import streamlit as st
import requests
import pandas as pd
import time

API_URL = "https://cropai-project.onrender.com"

st.set_page_config(
    page_title="CropAI",
    page_icon="🌾",
    layout="wide"
)

# =====================================================
# INITIAL SESSION STATE
# =====================================================
if "users" not in st.session_state:
    st.session_state.users = {}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "current_user" not in st.session_state:
    st.session_state.current_user = None

# =====================================================
# LOGIN / REGISTER
# =====================================================
if not st.session_state.logged_in:

    st.markdown("""
    <div class="hero">
        <h1>CropAI</h1>
        <p>Login to access your personal agriculture dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Login", "Register"])

    # LOGIN
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username in st.session_state.users and \
               st.session_state.users[username]["password"] == password:

                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER
    with tab2:
        new_user = st.text_input("Create Username")
        new_pass = st.text_input("Create Password", type="password")

        if st.button("Register"):
            if new_user in st.session_state.users:
                st.error("User already exists")
            else:
                st.session_state.users[new_user] = {
                    "password": new_pass,
                    "disease_count": 0,
                    "crop_count": 0,
                    "fert_count": 0,
                    "disease_history": {}
                }
                st.success("Account created! Please login.")

# =====================================================
# DASHBOARD (AFTER LOGIN)
# =====================================================
else:

    user = st.session_state.current_user
    user_data = st.session_state.users[user]

    st.sidebar.success(f"Logged in as {user}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.rerun()

    # HERO
    st.markdown(f"""
    <div class="hero">
        <h1>Welcome, {user}</h1>
        <p>Your personal AI agriculture dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    # METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("Disease Predictions", user_data["disease_count"])
    m2.metric("Crop Recommendations", user_data["crop_count"])
    m3.metric("Fertilizer Suggestions", user_data["fert_count"])

    st.markdown("---")

    # =================================================
    # DISEASE DETECTION
    # =================================================
    st.markdown("## 🩺 Disease Detection")

    uploaded_file = st.file_uploader("Upload Leaf Image", type=["jpg","jpeg","png"])

    if uploaded_file:
        st.image(uploaded_file, width=300)

        if st.button("Analyze Disease"):
            with st.spinner("Analyzing..."):
                files = {
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type
                    )
                }

                try:
                    resp = requests.post(f"{API_URL}/predict-disease", files=files)

                    if resp.status_code == 200:
                        data = resp.json()
                        label = data["disease_label"]
                        confidence = data["confidence"]

                        st.progress(confidence)
                        st.success(f"{label} ({confidence:.2f})")

                        user_data["disease_count"] += 1
                        user_data["disease_history"][label] = \
                            user_data["disease_history"].get(label, 0) + 1

                    else:
                        st.error(resp.text)

                except Exception as e:
                    st.error(e)

    # =================================================
    # ANALYTICS
    # =================================================
    st.markdown("---")
    st.markdown("## 📊 Your Analytics")

    col1, col2 = st.columns(2)

    with col1:
        usage_df = pd.DataFrame({
            "Feature": ["Disease", "Crop", "Fertilizer"],
            "Usage": [
                user_data["disease_count"],
                user_data["crop_count"],
                user_data["fert_count"]
            ]
        })
        st.bar_chart(usage_df.set_index("Feature"))

    with col2:
        if user_data["disease_history"]:
            disease_df = pd.DataFrame.from_dict(
                user_data["disease_history"],
                orient="index",
                columns=["Cases"]
            )
            st.bar_chart(disease_df)
        else:
            st.info("No disease data yet.")

    st.markdown("---")
    st.markdown(
        "<center style='color:#9ca3af;'>© 2026 CropAI • Personal AI Dashboard</center>",
        unsafe_allow_html=True
    )