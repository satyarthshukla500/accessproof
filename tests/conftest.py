import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("APP_SECRET", "test-secret-0123456789")
os.environ.setdefault("PAYPAL_CLIENT_ID", "x")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "x")
os.environ.setdefault("GEMINI_MODEL", "test-model")
os.environ.setdefault("GEMINI_API_KEY", "x")
