"""Vercel Python entry point -- re-exports the FastAPI app.

Static assets (static/*) are served directly by Vercel per vercel.json's
routes, not through this function, so only /api/* traffic reaches here.
"""
from app.main import app  # noqa: F401
