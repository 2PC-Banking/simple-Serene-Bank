"""
Lock Service - Quản lý khóa tài khoản trong 2PC
"""

from sqlalchemy.orm import Session
from app.models.account_model import Account
from app.utils.logger import log_transaction, log_error


class LockService:
    """Service quản lý việc lock/unlock tài khoản"""

    @staticmethod
    def lock_account(db: Session, account_id: str, transaction_id: str) -> bool:
        """
        Khóa tài khoản cho một transaction.
        Returns True nếu lock thành công, False nếu đã bị khóa.
        """
        account = db.query(Account).filter(Account.account_id == account_id).with_for_update().first()

        if account is None:
            log_error(transaction_id, "LOCK", f"Account '{account_id}' not found")
            return False

        if account.is_locked:
            # Cho phép cùng transaction lock lại
            if account.locked_by_tx == transaction_id:
                log_transaction(transaction_id, "LOCK", f"Account '{account_id}' already locked by this TX")
                return True
            log_error(transaction_id, "LOCK", f"Account '{account_id}' locked by '{account.locked_by_tx}'")
            return False

        account.is_locked = True
        account.locked_by_tx = transaction_id
        log_transaction(transaction_id, "LOCK", f"Account '{account_id}' locked successfully")
        return True

    @staticmethod
    def unlock_account(db: Session, account_id: str, transaction_id: str) -> bool:
        """
        Mở khóa tài khoản sau khi commit/rollback.
        Returns True nếu unlock thành công.
        """
        account = db.query(Account).filter(Account.account_id == account_id).first()

        if account is None:
            log_error(transaction_id, "UNLOCK", f"Account '{account_id}' not found")
            return False

        if not account.is_locked:
            log_transaction(transaction_id, "UNLOCK", f"Account '{account_id}' is already unlocked")
            return True

        if account.locked_by_tx != transaction_id:
            log_error(transaction_id, "UNLOCK", f"Account '{account_id}' is locked by different TX '{account.locked_by_tx}'")
            return False

        account.is_locked = False
        account.locked_by_tx = None
        log_transaction(transaction_id, "UNLOCK", f"Account '{account_id}' unlocked successfully")
        return True

    @staticmethod
    def is_locked(db: Session, account_id: str) -> tuple[bool, str | None]:
        """
        Kiểm tra tài khoản có bị khóa không.
        Returns (is_locked, locked_by_tx)
        """
        account = db.query(Account).filter(Account.account_id == account_id).first()
        if account is None:
            return False, None
        return account.is_locked, account.locked_by_tx
