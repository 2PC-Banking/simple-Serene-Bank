"""
Logger utility for Bank System 2PC
"""

import logging
import sys
from datetime import datetime


def setup_logger(name: str = "bank-2pc") -> logging.Logger:
    """Tạo và cấu hình logger"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Logger mặc định
logger = setup_logger()


def log_transaction(tx_id: str, action: str, detail: str = ""):
    """Log thông tin transaction"""
    logger.info(f"[TX:{tx_id}] {action} {detail}")


def log_error(tx_id: str, action: str, error: str):
    """Log lỗi transaction"""
    logger.error(f"[TX:{tx_id}] {action} FAILED - {error}")
