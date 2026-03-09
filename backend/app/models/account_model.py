"""
Account Model - SQLAlchemy ORM model for accounts table
"""

from sqlalchemy import Column, String, Numeric, Boolean, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "dbo"}

    account_id = Column(String(50), primary_key=True)
    account_name = Column(String(100), nullable=False)
    balance = Column(Numeric(18, 2), nullable=False, default=0.00)
    is_locked = Column(Boolean, nullable=False, default=False)
    locked_by_tx = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Account(id={self.account_id}, name={self.account_name}, balance={self.balance})>"

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "balance": float(self.balance),
            "is_locked": self.is_locked,
            "locked_by_tx": self.locked_by_tx,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
