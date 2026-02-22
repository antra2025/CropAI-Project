from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Dict

import numpy as np
from PIL import Image
import io
import joblib
import json
from tensorflow.keras.models import load_model

# -----------------------------
# Manual mappings for Fertilizer dataset
# (Verify with your dataset; these are standard for the Fertilizer_Prediction.csv)
# -----------------------------

SOIL_TYPE_MAP = {
    "Sandy": 0,
    "Loamy": 1,
    "Black": 2,
    "Red": 3,
    "Clayey": 4,
}

CROP_TYPE_MAP = {
    "Maize": 0,
    "Sugarcane": 1,
    "Cotton": 2,
    "Tobacco": 3,
    "Paddy": 4,
    "Barley": 5,
    "Wheat": 6,
}


# -----------------------------
# Paths
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # CropAI-Project root
MODELS_DIR = BASE_DIR / "models"

# If your disease model is .keras instead of .h5, change the filename here
CROP_DISEASE_MODEL_PATH = MODELS_DIR / "crop_disease_best.h5"

CROP_MODEL_PATH = MODELS_DIR / "crop_recommendation_model.pkl"
CROP_SCALER_PATH = MODELS_DIR / "crop_scaler.pkl"
CROP_LABEL_ENCODER_PATH = MODELS_DIR / "crop_label_encoder.pkl"

FERT_MODEL_PATH = MODELS_DIR / "fertilizer_recommendation_model.pkl"
FERT_SCALER_PATH = MODELS_DIR / "fert_scaler.pkl"
FERT_LABEL_ENCODER_PATH = MODELS_DIR / "fert_label_encoder.pkl"
FERT_CAT_ENCODERS_PATH = MODELS_DIR / "fert_categorical_encoders.pkl"


CLASS_MAPPING_PATH = MODELS_DIR / "disease_class_mapping.json"


IMG_SIZE = (224, 224)  # same as used in training


# -----------------------------
# Pydantic models (request bodies)
# -----------------------------

class CropInput(BaseModel):
    N: float
    P: float
    K: float
    temperature: float
    humidity: float
    ph: float
    rainfall: float


class FertilizerInput(BaseModel):
    # Use the same names as training dataset (after cleaning)
    Temparature: float
    Humidity: float
    Moisture: float
    Soil_Type: str
    Crop_Type: str
    Nitrogen: float
    Potassium: float
    Phosphorous: float


# -----------------------------
# FastAPI app initialization
# -----------------------------

app = FastAPI(title="Crop AI Backend")

# Allow frontend / mobile app to call this API (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Load models at startup
# -----------------------------

print("Loading models...")

try:
    crop_disease_model = load_model(CROP_DISEASE_MODEL_PATH)

    with open(CLASS_MAPPING_PATH, "r") as f:
        disease_class_map = json.load(f)

    crop_model = joblib.load(CROP_MODEL_PATH)
    crop_scaler = joblib.load(CROP_SCALER_PATH)
    crop_label_encoder = joblib.load(CROP_LABEL_ENCODER_PATH)

    fert_model = joblib.load(FERT_MODEL_PATH)
    fert_scaler = joblib.load(FERT_SCALER_PATH)
    fert_label_encoder = joblib.load(FERT_LABEL_ENCODER_PATH)
    fert_cat_encoders: Dict[str, object] = joblib.load(FERT_CAT_ENCODERS_PATH)

    print("✅ All models loaded successfully.")

except Exception as e:
    print("❌ Error loading models:", e)
    # Let app still start, we will raise error on endpoints if models missing
    crop_disease_model = None
    disease_class_map = {}

    crop_model = None
    crop_scaler = None
    crop_label_encoder = None
    fert_model = None
    fert_scaler = None
    fert_label_encoder = None
    fert_cat_encoders = None





# -----------------------------
# Helper functions
# -----------------------------

def preprocess_image_for_disease(file_bytes: bytes) -> np.ndarray:
    """Convert uploaded image bytes into model-ready numpy array."""
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img = img.resize(IMG_SIZE)
    arr = np.array(img) / 255.0
    arr = np.expand_dims(arr, axis=0)  # (1, H, W, 3)
    return arr


def encode_fertilizer_features(data: FertilizerInput) -> np.ndarray:
    """Encode input features for fertilizer recommendation.

    Soil_Type and Crop_Type are received as human-readable strings (e.g. 'Loamy', 'Sugarcane')
    and mapped to the numeric codes used during model training.
    """
    # Map soil type string to numeric code
    try:
        soil_code = SOIL_TYPE_MAP[data.Soil_Type]
    except KeyError:
        valid = list(SOIL_TYPE_MAP.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Soil_Type: {data.Soil_Type}. Valid values: {valid}",
        )

    # Map crop type string to numeric code
    try:
        crop_code = CROP_TYPE_MAP[data.Crop_Type]
    except KeyError:
        valid = list(CROP_TYPE_MAP.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Crop_Type: {data.Crop_Type}. Valid values: {valid}",
        )

    # Build feature vector in the same order as training:
    # Temparature, Humidity, Moisture, Soil_Type, Crop_Type, Nitrogen, Potassium, Phosphorous
    features = [
        data.Temparature,
        data.Humidity,
        data.Moisture,
        soil_code,
        crop_code,
        data.Nitrogen,
        data.Potassium,
        data.Phosphorous,
    ]

    return np.array(features).reshape(1, -1)





# -----------------------------
# Routes
# -----------------------------

@app.get("/")
def root():
    return {"message": "Crop AI Backend is running."}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict-disease")
async def predict_disease(file: UploadFile = File(...)):
    """Predict crop disease from uploaded image."""
    if crop_disease_model is None:
        raise HTTPException(status_code=500, detail="Disease model not loaded on server.")

    file_bytes = await file.read()
    img_arr = preprocess_image_for_disease(file_bytes)

    preds = crop_disease_model.predict(img_arr)
    class_index = int(np.argmax(preds[0]))
    confidence = float(np.max(preds[0]))

    # Use the mapping loaded from disease_class_mapping.json
    # Keys in JSON are strings, so we use str(class_index)
    label = disease_class_map.get(str(class_index), f"class_{class_index}")

    return {
        "predicted_class_index": class_index,
        "disease_label": label,
        "confidence": confidence
    }



@app.post("/recommend-crop")
def recommend_crop(data: CropInput):
    """Recommend a crop based on soil & climate."""
    if crop_model is None or crop_scaler is None or crop_label_encoder is None:
        raise HTTPException(status_code=500, detail="Crop recommendation model or scaler not loaded.")

    # Feature order must match training: [N, P, K, temperature, humidity, ph, rainfall]
    X = np.array([[data.N, data.P, data.K,
                   data.temperature, data.humidity,
                   data.ph, data.rainfall]])

    X_scaled = crop_scaler.transform(X)
    pred_encoded = crop_model.predict(X_scaled)
    crop_name = crop_label_encoder.inverse_transform(pred_encoded)[0]

    return {
        "recommended_crop": crop_name
    }


@app.post("/recommend-fertilizer")
def recommend_fertilizer(data: FertilizerInput):
    """Recommend fertilizer based on soil, crop and conditions."""
    if fert_model is None or fert_scaler is None or fert_label_encoder is None or fert_cat_encoders is None:
        raise HTTPException(status_code=500, detail="Fertilizer model or encoders not loaded.")

    try:
        X = encode_fertilizer_features(data)
        X_scaled = fert_scaler.transform(X)
        pred_encoded = fert_model.predict(X_scaled)
    except HTTPException:
        # Re-raise HTTPExceptions as-is so client sees the message
        raise
    except Exception as e:
        # Any other unexpected error
        raise HTTPException(status_code=500, detail=f"Unexpected error in fertilizer prediction: {e}")

    fert_name = fert_label_encoder.inverse_transform(pred_encoded)[0]

    return {
        "recommended_fertilizer": fert_name
    }


# Uncomment this if you want to run with `python main.py`
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
