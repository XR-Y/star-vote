# FastAPI entrypoint for Vercel auto-detection.
try:
    from .main import app
except ImportError:
    from api.main import app
