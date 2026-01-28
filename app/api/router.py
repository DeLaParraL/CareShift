"""
api router

this file is basically the "table of contents" for all endpoints.

why we do this:
- main.py stays clean (just creates the app and includes this router)
- routes are grouped by feature (health, schedule, demo, etc.)
- scaling is easier when more people contribute
"""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.schedule import router as schedule_router
from app.api.routes.demo import router as demo_router

api_router = APIRouter()

# health checks and sanity endpoints
api_router.include_router(health_router, tags=["health"])

# scheduling endpoints (the main feature)
api_router.include_router(schedule_router, tags=["schedule"])

# demo endpoints exist to make the project easy to try in swagger
api_router.include_router(demo_router, tags=["demo"])