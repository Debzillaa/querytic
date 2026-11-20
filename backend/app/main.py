from fastapi import FastAPI

from app.api.datasets import router as datasets_router

app = FastAPI(
    title="Querytic API",
    description="Backend API for the Querytic Data Analytics Platform",
    version="0.1.0",
)

app.include_router(datasets_router)


@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy", "message": "Welcome to Querytic API"}