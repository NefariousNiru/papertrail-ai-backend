# routes.py
from fastapi import FastAPI
from controller.validation_controller import validation_router


def register_routes(app: FastAPI) -> None:
    """Register & Access control controllers here."""
    app.include_router(validation_router)
