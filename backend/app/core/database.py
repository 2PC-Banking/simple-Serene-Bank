from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from contextlib import contextmanager
from typing import Generator
import os

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


def create_database_if_not_exists() -> bool:
    """
    Tạo database BankDB nếu chưa tồn tại.
    Kết nối vào master database để tạo.
    """

    # Connection string để kết nối vào master database
    master_url = (
        f"mssql+pyodbc://@{settings.DB_SERVER}/master?"
        f"driver={settings.DB_DRIVER.replace(' ', '+')}&"
        f"Trusted_Connection=yes"
    )

    try:
        # Sử dụng isolation_level=AUTOCOMMIT để tránh lỗi transaction
        master_engine = create_engine(master_url, isolation_level="AUTOCOMMIT")
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

    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "database",
        "schema.sql"
    )
    
    if not os.path.exists(schema_path):
        print(f"Schema file not found: {schema_path}")
        return
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    # Loại bỏ các lệnh CREATE DATABASE và USE vì đã xử lý riêng
    # Chỉ giữ lại các lệnh tạo bảng và triggers
    batches = schema_sql.split("\nGO")
    
    # Tạo engine mới kết nối trực tiếp vào BankDB
    db_url = (
        f"mssql+pyodbc://@{settings.DB_SERVER}/{settings.DB_NAME}?"
        f"driver={settings.DB_DRIVER.replace(' ', '+')}&"
        f"Trusted_Connection=yes"
    )
    db_engine = create_engine(db_url)

    with db_engine.connect() as conn:
        for batch in batches:
            batch = batch.strip()
            # Bỏ qua các lệnh CREATE DATABASE, USE
            if batch and not batch.startswith("--"):
                if "CREATE DATABASE" in batch.upper() or batch.upper().startswith("USE "):
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
