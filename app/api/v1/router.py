"""Aggregate all v1 routers under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.routes import (
    attendance, auth, branches, catalog, dashboard, inventory, memberships,
    notifications, payments, seats, settings, staff, students,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(students.router)
api_router.include_router(catalog.router)
api_router.include_router(seats.router)
api_router.include_router(attendance.router)
api_router.include_router(payments.router)
api_router.include_router(notifications.router)
api_router.include_router(settings.router)
api_router.include_router(memberships.router)
api_router.include_router(inventory.router)
api_router.include_router(staff.router)
api_router.include_router(branches.router)
