"""
Recovery Service - Khôi phục trạng thái sau crash/restart
Xử lý các transaction PREPARED còn treo khi hệ thống khởi động lại.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.account_model import Account
from app.models.transaction_model import TransactionLog
from app.core.database import get_db_context
from app.core.config import settings
from app.utils.logger import log_transaction, logger


class RecoveryService:
    """Service phục hồi transaction sau crash"""

    @staticmethod
    def list_pending_transactions() -> dict:
        """
        List all transactions currently in PREPARED state awaiting coordinator decision.

        These transactions have completed Phase 1 (PREPARE) but have not yet
        received COMMIT or ROLLBACK from the coordinator. They hold account locks
        and must be resolved either by the coordinator or via force-rollback.

        Returns dict with pending count and details.
        """
        logger.info("=== RECOVERY: Listing pending (PREPARED) transactions ===")

        with get_db_context() as db:
            prepared_txs = db.query(TransactionLog).filter(
                TransactionLog.status == "PREPARED"
            ).all()

            if not prepared_txs:
                logger.info("RECOVERY: No pending transactions found")
                return {
                    "pending": 0,
                    "details": []
                }

            logger.info(f"RECOVERY: Found {len(prepared_txs)} pending transaction(s)")

            details = []
            for tx in prepared_txs:
                detail = {
                    "transaction_id": tx.transaction_id,
                    "account_id": tx.account_id,
                    "operation": tx.operation,
                    "amount": float(tx.amount),
                    "status": tx.status,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
                details.append(detail)
                log_transaction(
                    tx.transaction_id,
                    "RECOVERY",
                    f"Pending TX: account={tx.account_id}, op={tx.operation}, amount={tx.amount}"
                )

            return {
                "pending": len(prepared_txs),
                "details": details
            }

    @staticmethod
    def auto_rollback_expired() -> dict:
        """
        Tự động rollback các transaction PREPARED đã quá timeout.
        Dùng LOCK_TIMEOUT từ config (mặc định 30 giây).
        """
        timeout_seconds = settings.LOCK_TIMEOUT
        logger.info(f"=== RECOVERY: Auto-rollback expired transactions (timeout={timeout_seconds}s) ===")

        with get_db_context() as db:
            # Tìm các TX PREPARED đã quá timeout
            cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
            expired_txs = db.query(TransactionLog).filter(
                TransactionLog.status == "PREPARED",
                TransactionLog.created_at < cutoff
            ).all()

            if not expired_txs:
                logger.info("RECOVERY: No expired transactions found")
                return {
                    "rolled_back_count": 0,
                    "transaction_ids": [],
                    "timeout_seconds": timeout_seconds
                }

            rolled_back = []
            for tx in expired_txs:
                tx.status = "ABORTED"

                account = db.query(Account).filter(
                    Account.account_id == tx.account_id
                ).first()

                if account and account.is_locked and account.locked_by_tx == tx.transaction_id:
                    account.is_locked = False
                    account.locked_by_tx = None

                rolled_back.append({
                    "transaction_id": tx.transaction_id,
                    "account_id": tx.account_id,
                    "operation": tx.operation,
                    "age_seconds": (datetime.now() - tx.created_at).total_seconds()
                })
                log_transaction(tx.transaction_id, "AUTO_ROLLBACK",
                                f"Expired after {timeout_seconds}s — account '{tx.account_id}' unlocked")

            db.commit()

        logger.info(f"RECOVERY: Auto-rolled back {len(rolled_back)} expired transaction(s)")
        return {
            "rolled_back_count": len(rolled_back),
            "transaction_ids": [r["transaction_id"] for r in rolled_back],
            "details": rolled_back,
            "timeout_seconds": timeout_seconds
        }

    @staticmethod
    def force_rollback_all_prepared() -> dict:
        """
        Force rollback tất cả transaction PREPARED.
        Dùng khi cần cleanup toàn bộ.
        """
        logger.info("=== RECOVERY: Force rollback all PREPARED transactions ===")

        with get_db_context() as db:
            prepared_txs = db.query(TransactionLog).filter(
                TransactionLog.status == "PREPARED"
            ).all()

            rolled_back = []
            for tx in prepared_txs:
                # Cập nhật status → ABORTED
                tx.status = "ABORTED"

                # Unlock account
                account = db.query(Account).filter(
                    Account.account_id == tx.account_id
                ).first()

                if account and account.is_locked and account.locked_by_tx == tx.transaction_id:
                    account.is_locked = False
                    account.locked_by_tx = None

                rolled_back.append(tx.transaction_id)
                log_transaction(tx.transaction_id, "FORCE_ROLLBACK", f"Account '{tx.account_id}' unlocked")

            db.commit()

        logger.info(f"RECOVERY: Force rolled back {len(rolled_back)} transaction(s)")
        return {
            "rolled_back_count": len(rolled_back),
            "transaction_ids": rolled_back
        }

    @staticmethod
    def cleanup_stale_locks() -> dict:
        """
        Dọn dẹp các lock cũ mà không có transaction PREPARED tương ứng.
        """
        logger.info("=== RECOVERY: Cleaning up stale locks ===")

        with get_db_context() as db:
            locked_accounts = db.query(Account).filter(Account.is_locked == True).all()

            cleaned = []
            for account in locked_accounts:
                if account.locked_by_tx:
                    # Kiểm tra có transaction PREPARED nào tương ứng không
                    tx = db.query(TransactionLog).filter(
                        TransactionLog.transaction_id == account.locked_by_tx,
                        TransactionLog.status == "PREPARED"
                    ).first()

                    if tx is None:
                        # Không có transaction, unlock account
                        account.is_locked = False
                        old_tx = account.locked_by_tx
                        account.locked_by_tx = None
                        cleaned.append({
                            "account_id": account.account_id,
                            "was_locked_by": old_tx
                        })
                        logger.info(f"RECOVERY: Cleaned stale lock on account '{account.account_id}' (was locked by '{old_tx}')")

            db.commit()

        return {
            "cleaned_count": len(cleaned),
            "details": cleaned
        }
