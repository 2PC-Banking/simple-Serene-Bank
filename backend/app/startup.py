"""
Startup module - Initialization tasks when the application starts
"""

from app.core.database import test_connection, init_db, seed_db, create_database_if_not_exists
from app.services.recovery_service import RecoveryService
from app.utils.logger import logger


def run_startup():
    """
    Chạy các tác vụ khởi động:
    1. Tạo database nếu chưa có
    2. Khởi tạo schema
    3. Seed data
    4. Test connection
    5. Recovery check
    """
    logger.info("=== Starting Bank System 2PC ===")

    # 1. Tạo database
    logger.info("Step 1: Creating database if not exists...")
    if not create_database_if_not_exists():
        logger.error("Cannot create database!")
        return False

    # 2. Khởi tạo schema
    logger.info("Step 2: Initializing database schema...")
    init_db()

    # 3. Seed data
    logger.info("Step 3: Seeding database...")
    seed_db()

    # 4. Test connection
    logger.info("Step 4: Testing database connection...")
    if not test_connection():
        logger.error("Database connection failed!")
        return False
    logger.info("Database connection successful")

    # 5. Recovery
    logger.info("Step 5: Checking for pending transactions...")
    try:
        result = RecoveryService.recover_pending_transactions()
        if result["pending"] > 0:
            logger.warning(f"Found {result['pending']} pending transaction(s)!")
            for detail in result["details"]:
                logger.warning(
                    f"  - TX: {detail['transaction_id']}, "
                    f"Account: {detail['account_id']}, "
                    f"Op: {detail['operation']}, "
                    f"Amount: {detail['amount']}"
                )
        else:
            logger.info("No pending transactions found")
    except Exception as e:
        logger.warning(f"Recovery check failed: {e}")

    logger.info("=== Bank System 2PC started successfully ===")
    return True
