# routes.py
from fastapi import FastAPI
from controller.paper_controller import paper_router
from controller.semantic_search_controller import semantic_search_router
from controller.validation_controller import validation_router


def register_routes(app: FastAPI) -> None:
    """Register & Access control controllers here."""
    app.include_router(validation_router)
    app.include_router(paper_router)
    app.include_router(semantic_search_router)
