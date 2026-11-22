from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.datasets import router as datasets_router
from app.core.database import Base, engine, get_db
from app.models import dataset as _dataset_model  # noqa: F401 (registers model with Base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Querytic API",
    description="Backend API for the Querytic Data Analytics Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(datasets_router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying both API and PostgreSQL connectivity.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed.",
        ) from exc

    return {
        "status": "healthy",
        "database": "connected",
        "message": "Welcome to Querytic API",
    }