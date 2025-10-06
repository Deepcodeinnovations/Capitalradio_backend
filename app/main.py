from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from app.models import *
from app.routes import api_router
from app.database import init_models, close_models, get_database

import logging
import os


app = FastAPI(
    title="Capital Radio App System",
    description="Backend API for Captal Radio Application",
    version="1.0.0",
    openapi_extra={
        "x-upload-size-limit": 5000 * 1024 * 1024,  # 5000 MB
    }
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)   
logger = logging.getLogger("uvicorn")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001","http://localhost:3002","http://localhost:3003",'https://kiis1009.co.ug','https://www.beatradio.co.ug','https://capitalradio.co.ug','https://admin.capitalradio.co.ug'],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


# Static files configuration
STATIC_DIR = "static"
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True)

# Mount static directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    return RedirectResponse("https://capitalradio.co.ug/", status_code=302)


@app.get("/recordings/health")
async def detailed_recording_status():
    """Detailed recording status"""
    return recording_service.get_health_check()


app.include_router(api_router, prefix="/api/v1")
# Startup and shutdown events
@app.on_event("startup")
async def startup():
    try:
        logger.info("Initializing application...")
        await init_models()
        logger.info("Application startup completed successfully")
      
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown():
    try:
        logger.info("Shutting down application...")
        await close_models()
        logger.info("Application shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"Shutdown failed: {e}", exc_info=True)
        raise