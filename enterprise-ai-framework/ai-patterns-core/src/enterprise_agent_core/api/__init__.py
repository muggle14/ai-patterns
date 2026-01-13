"""API module for Enterprise Agent.

Provides FastAPI application factory and routes for the Enterprise Agent.
"""

from .app import create_app
from .routes import router

__all__ = ["create_app", "router"]
