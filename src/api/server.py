"""FastAPI application entrypoint.

Run: uvicorn src.api.server:app --reload
Serves the catalog/search API backed by PostgreSQL (DATABASE_URL).
"""
import os

from fastapi import FastAPI

from .routes import router

app = FastAPI(title="Open Project Directory API", version="0.1.0")
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"service": "open-project-directory", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
