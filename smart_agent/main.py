"""
FastAPI application entry point for the Old Fashioned Agent.

Provides a REST API for the Agreus Family Office Benchmark Agent
with Anthropic API integration and conversation threading support.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.routes.routes import router
from src.config.logger import Logger

logger = Logger()

# Configuration
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
ALLOW_ORIGINS = os.environ.get("ALLOW_ORIGINS", "http://localhost:3000").split(",")

# Create FastAPI app
app = FastAPI(
    title="Agreus Family Office Benchmark Agent",
    description="Old Fashioned Agent for family office compensation benchmarks using Anthropic API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Agreus Family Office Benchmark Agent")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT_MODE', 'dev')}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down agent")


# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
