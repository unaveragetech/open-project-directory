"""FastAPI routes: project lookup, search, submission intake."""
from fastapi import APIRouter, HTTPException

router = APIRouter()

# The API serves the catalog from PostgreSQL in production. These routes
# define the contract; wiring to a session is done in server.py.
# For the static prototype, data/projects.json is the catalog.


@router.get("/projects")
def list_projects(q=None, category=None, open_source=None):
    """Search/list projects. Implemented against the DB session in server.py."""
    raise NotImplementedError("wire to database session in server.py")


@router.get("/projects/{slug}")
def get_project(slug: str):
    raise NotImplementedError("wire to database session in server.py")


@router.get("/health")
def health():
    return {"status": "ok"}
