from fastapi import FastAPI

# Initialize the FastAPI application
app = FastAPI(
    title="Querytic API",
    description="Backend API for the Querytic Data Analytics Platform",
    version="0.1.0"
)

# Define a simple health-check endpoint
@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy", "message": "Welcome to Querytic API"}