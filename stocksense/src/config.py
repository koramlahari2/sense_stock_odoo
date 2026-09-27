"""
Central configuration + Firebase initialization.

Nothing in this file is a secret by itself - it just reads values that
YOU provide in a local .env file (never committed to git).

Where your keys actually go:
- Web/client Firebase config -> .env  (FIREBASE_* variables)
- Service account JSON (admin credential) -> ./secrets/firebase-service-account.json
    referenced by GOOGLE_APPLICATION_CREDENTIALS in .env
- Gemini API key -> .env, read ONLY here on the server side.
  They are never sent to the browser because Streamlit renders server-side;
  the key never appears in any HTML/JS delivered to the client.
"""
import json
import os
from pathlib import Path

import firebase_admin
import pyrebase
import streamlit as st
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

load_dotenv()

FIREBASE_WEB_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL", ""),
}

SERVICE_ACCOUNT_PATH = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS", "./secrets/firebase-service-account.json"
)
FIRESTORE_DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "(default)")

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def _resolve_service_account_path():
    if not SERVICE_ACCOUNT_PATH:
        raise FileNotFoundError("GOOGLE_APPLICATION_CREDENTIALS is not configured in .env.")

    path = Path(SERVICE_ACCOUNT_PATH)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Firebase service account file not found at '{path}'. "
            "Download it from Firebase Console > Project Settings > Service Accounts, "
            "save it there, and set GOOGLE_APPLICATION_CREDENTIALS in .env."
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(
            f"Firebase service account file is invalid or unreadable at '{path}'. "
            "Use the JSON downloaded from Firebase Console > Project Settings > Service Accounts."
        ) from exc

    if payload is None or not isinstance(payload, dict) or payload.get("type") != "service_account":
        raise ValueError(
            f"Firebase service account file at '{path}' is not a valid service account JSON. "
            "Download the real JSON from Firebase Console > Project Settings > Service Accounts."
        )

    return str(path)


def _check_config():
    missing = [k for k, v in FIREBASE_WEB_CONFIG.items() if not v and k != "databaseURL"]
    if missing:
        st.error(
            "Missing Firebase web config values: "
            + ", ".join(missing)
            + ". Fill them in your .env file (copy from .env.example)."
        )
        st.stop()

    try:
        _resolve_service_account_path()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()


@st.cache_resource
def get_pyrebase_auth():
    """Client-side style auth (signup/login/reset password) via Firebase REST API."""
    _check_config()
    firebase = pyrebase.initialize_app(FIREBASE_WEB_CONFIG)
    return firebase.auth()


@st.cache_resource
def get_firestore_client():
    """Admin SDK Firestore client - full read/write, used for all app data."""
    _check_config()
    service_account_path = _resolve_service_account_path()
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    return firestore.client(database_id=FIRESTORE_DATABASE_ID)


def get_ai_client():
    """Return the configured Gemini client without exposing its key to the UI."""
    if AI_PROVIDER != "gemini" or not GEMINI_API_KEY:
        return None, None
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    return "gemini", genai
