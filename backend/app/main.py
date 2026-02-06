"""
Bank System - 2PC (Two Phase Commit) Participant
Main application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.core.database import test_connection, init_db, seed_db, create_database_if_not_exists

# Tạo FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Bank System Participant for Two-Phase Commit Protocol",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Khởi động ứng dụng"""
    print(f"Starting {settings.APP_NAME}...")

    # Tạo database nếu chưa có
    print("Creating database if not exists...")
    if not create_database_if_not_exists():
        print("✗ Cannot create database")
        return

    # Khởi tạo schema
    print("Initializing database schema...")
    init_db()

    # Seed data
    print("Seeding database...")
    seed_db()

    # Test connection
    if test_connection():
        print("✓ Database connection successful")
    else:
        print("✗ Database connection failed")
        return

    print(f"✓ {settings.APP_NAME} started on port {settings.APP_PORT}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "port": settings.APP_PORT
    }


@app.get("/health")
async def health_check():
    """Health check with database status"""
    db_status = test_connection()
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "service": settings.APP_NAME
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
