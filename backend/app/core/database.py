from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from contextlib import contextmanager
from typing import Generator
import os
import re
from pathlib import Path

from .config import settings

# Tạo engine kết nối SQL Server
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,        # Kiểm tra connection trước khi sử dụng
    pool_size=10,              # Số connection trong pool
    max_overflow=20,           # Số connection tối đa vượt pool
    pool_recycle=3600,         # Recycle connection sau 1 giờ
    echo=settings.DEBUG        # Log SQL queries nếu DEBUG=True
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

# Base class cho models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency để lấy database session.
    Sử dụng trong FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager để lấy database session.
    Sử dụng trong services.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """Kiểm tra kết nối database"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def _clean_sql_batch(batch: str) -> str:
    """Loại bỏ comment line (`--`) để giữ lại câu SQL thực thi được."""
    lines = []
    for line in batch.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def create_database_if_not_exists() -> bool:
    """
    Tạo database BankDB nếu chưa tồn tại.
    Kết nối vào master database để tạo.
    """

    try:
        # Sử dụng isolation_level=AUTOCOMMIT để tránh lỗi transaction
        master_engine = create_engine(settings.MASTER_DATABASE_URL, isolation_level="AUTOCOMMIT")
        with master_engine.connect() as conn:
            # Kiểm tra database có tồn tại không
            result = conn.execute(text(
                f"SELECT name FROM sys.databases WHERE name = '{settings.DB_NAME}'"
            ))
            if result.fetchone() is None:
                # Tạo database mới
                conn.execute(text(f"CREATE DATABASE {settings.DB_NAME}"))
                print(f"✓ Database '{settings.DB_NAME}' created successfully!")
            else:
                print(f"✓ Database '{settings.DB_NAME}' already exists")
        master_engine.dispose()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False


def init_db() -> None:
    """
    Khởi tạo database - tạo các bảng từ schema.sql
    """
    # Đầu tiên tạo database nếu chưa có
    if not create_database_if_not_exists():
        print("Cannot create database, skipping schema initialization")
        return

    # Nếu schema đã tồn tại thì không tạo lại để tránh mất dữ liệu.
    try:
        with engine.connect() as conn:
            accounts_exists = conn.execute(text("SELECT OBJECT_ID('dbo.accounts', 'U')")).scalar() is not None
            tx_log_exists = conn.execute(text("SELECT OBJECT_ID('dbo.transaction_log', 'U')")).scalar() is not None
            if accounts_exists and tx_log_exists:
                print("✓ Schema already exists, skipping initialization")
                return
    except Exception as e:
        print(f"Error checking existing schema: {e}")

    current_file = Path(__file__).resolve()
    candidate_paths = [
        current_file.parents[3] / "database" / "schema.sql",  # local: repo/backend/app/core -> repo/database
        current_file.parents[2] / "database" / "schema.sql",  # docker: /app/app/core -> /app/database
    ]
    schema_path = next((p for p in candidate_paths if p.exists()), None)

    if schema_path is None:
        print(f"Schema file not found. Tried: {', '.join(str(p) for p in candidate_paths)}")
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Tách batch theo GO (cả file dùng LF/CRLF).
    # Trước đó split theo "\nGO" khiến một số batch có comment đầu bị bỏ qua.
    batches = re.split(r"^\s*GO\s*$", schema_sql, flags=re.MULTILINE)
    db_engine = create_engine(settings.DATABASE_URL)

    with db_engine.connect() as conn:
        for batch in batches:
            batch = _clean_sql_batch(batch)
            # Bỏ qua các lệnh CREATE DATABASE, USE
            if not batch:
                continue
            upper_batch = batch.upper()
            if "CREATE DATABASE" in upper_batch or upper_batch.startswith("USE "):
                continue
            try:
                conn.execute(text(batch))
                conn.commit()
            except Exception as e:
                print(f"Error executing batch: {e}")
                conn.rollback()

    db_engine.dispose()
    print("Database schema initialized successfully!")


def seed_db() -> None:
    """
    Chèn dữ liệu mẫu nếu bảng accounts trống
    """
    # Kiểm tra xem bảng accounts có dữ liệu chưa
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM dbo.accounts"))
            count = result.scalar()
            if count > 0:
                print(f"✓ Table 'accounts' already has {count} records, skipping seed")
                return
    except Exception as e:
        print(f"Error checking accounts table: {e}")
        return

    # Insert dữ liệu trực tiếp
    insert_sql = """
    INSERT INTO dbo.accounts (account_id, account_name, balance, is_locked, locked_by_tx)
    VALUES 
        ('ACC001', N'Nguyễn Văn A', 10000000.00, 0, NULL),
        ('ACC002', N'Trần Thị B', 5000000.00, 0, NULL),
        ('ACC003', N'Lê Văn C', 15000000.00, 0, NULL),
        ('ACC004', N'Phạm Thị D', 8000000.00, 0, NULL),
        ('ACC005', N'Hoàng Văn E', 20000000.00, 0, NULL)
    """

    try:
        with engine.connect() as conn:
            conn.execute(text(insert_sql))
            conn.commit()
            print("✓ Seed data inserted successfully!")
    except Exception as e:
        print(f"Error seeding data: {e}")
