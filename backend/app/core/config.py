from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str = "localhost"
    DB_NAME: str = "BankDB"

    # App
    APP_NAME: str = "Bank-2PC"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    DEBUG: bool = True

    LOCK_TIMEOUT: int = 30

    @property
    def DATABASE_URL(self) -> str:
        print("🔐 Using Windows Authentication")
        return (
            f"mssql+pyodbc://@{self.DB_SERVER}/{self.DB_NAME}?"
            f"driver={self.DB_DRIVER.replace(' ', '+')}&"
            "Trusted_Connection=yes&"
            "Encrypt=no&TrustServerCertificate=yes"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
