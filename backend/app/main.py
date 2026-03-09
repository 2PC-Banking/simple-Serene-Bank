"""
Bank System - 2PC (Two Phase Commit) Participant
Main application entry point
"""

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.core.database import test_connection, init_db, seed_db, create_database_if_not_exists
from app.api import balance, prepare, commit, rollback, single_bank
from app.services.recovery_service import RecoveryService

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

    # Recovery: kiểm tra transaction pending
    print("Checking for pending transactions (recovery)...")
    try:
        recovery_result = RecoveryService.recover_pending_transactions()
        if recovery_result["pending"] > 0:
            print(f"⚠ Found {recovery_result['pending']} pending transaction(s)")
        else:
            print("✓ No pending transactions")
    except Exception as e:
        print(f"⚠ Recovery check failed: {e}")

    print(f"✓ {settings.APP_NAME} started on port {settings.APP_PORT}")

    # Background task: auto-rollback expired transactions
    asyncio.create_task(periodic_auto_rollback())


async def periodic_auto_rollback():
    """Background task: kiểm tra và rollback các TX PREPARED đã quá timeout"""
    while True:
        await asyncio.sleep(settings.LOCK_TIMEOUT)
        try:
            result = RecoveryService.auto_rollback_expired()
            if result["rolled_back_count"] > 0:
                print(f"⚠ Auto-rolled back {result['rolled_back_count']} expired transaction(s)")
        except Exception as e:
            print(f"⚠ Auto-rollback check failed: {e}")


# =============================================
# Register API Routers
# =============================================
app.include_router(balance.router)
app.include_router(prepare.router)
app.include_router(commit.router)
app.include_router(rollback.router)
app.include_router(single_bank.router)


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
