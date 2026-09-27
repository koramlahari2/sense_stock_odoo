"""Authentication using Firebase Auth (via pyrebase for email/password REST calls)."""
import streamlit as st
from firebase_admin import firestore
from src.config import get_pyrebase_auth, get_firestore_client

DEFAULT_ROLE = "warehouse_staff"


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    lower_msg = msg.lower()

    if "service account" in lower_msg or "google_application_credentials" in lower_msg or "firebase service account file" in lower_msg:
        return (
            "Firebase admin credentials are missing or invalid. "
            "Download the real service-account JSON from Firebase Console > Project Settings > Service Accounts."
        )

    if "OPERATION_NOT_ALLOWED" in msg:
        return "Email/password sign-in is disabled. Enable it in Firebase Console > Authentication > Sign-in method."
    if "USER_DISABLED" in msg:
        return "This Firebase account is disabled. Enable it in Firebase Console > Authentication > Users."
    if "INVALID_API_KEY" in msg or "API key not valid" in msg:
        return "The Firebase web API key is invalid. Copy the Web app config from Firebase Project Settings."
    if "PERMISSION_DENIED" in msg or "insufficient permissions" in lower_msg:
        return "Firebase denied this request. Check Firestore rules and the service-account project."
    if "network" in lower_msg or "connection" in lower_msg:
        return "Could not reach Firebase. Check your internet connection and Firebase project settings."

    mapping = {
        "EMAIL_EXISTS": "An account with this email already exists.",
        "EMAIL_NOT_FOUND": "No account found with this email.",
        "INVALID_PASSWORD": "Incorrect password.",
        "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
        "WEAK_PASSWORD": "Password should be at least 6 characters.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again later.",
        "INVALID_EMAIL": "Please enter a valid email address.",
    }
    for key, friendly in mapping.items():
        if key in msg:
            return friendly
    return f"Firebase request failed: {msg or 'unknown error'}"


def sign_up(email: str, password: str, full_name: str, role: str = DEFAULT_ROLE):
    try:
        auth = get_pyrebase_auth()
        db = get_firestore_client()
        user = auth.create_user_with_email_and_password(email, password)
        uid = user["localId"]
        db.collection("users").document(uid).set({
            "email": email,
            "fullName": full_name,
            "role": role,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return True, "Account created! Please log in."
    except Exception as e:
        return False, _friendly_error(e)


def sign_in(email: str, password: str):
    try:
        auth = get_pyrebase_auth()
        db = get_firestore_client()
        user = auth.sign_in_with_email_and_password(email, password)
        uid = user["localId"]
        profile = db.collection("users").document(uid).get()
        profile_data = profile.to_dict() or {} if profile.exists else {}
        st.session_state["user"] = {
            "uid": uid,
            "email": email,
            "idToken": user["idToken"],
            "fullName": profile_data.get("fullName", email.split("@")[0]),
            "role": profile_data.get("role", DEFAULT_ROLE),
        }
        return True, "Logged in successfully."
    except Exception as e:
        return False, _friendly_error(e)


def send_password_reset(email: str):
    try:
        auth = get_pyrebase_auth()
        auth.send_password_reset_email(email)
        return True, "Password reset email sent. Check your inbox."
    except Exception as e:
        return False, _friendly_error(e)


def sign_out():
    st.session_state.pop("user", None)


def current_user():
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return "user" in st.session_state
