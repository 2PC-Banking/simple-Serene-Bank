from functools import lru_cache
import json
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str = "localhost\\SQLEXPRESS"
    DB_NAME: str = "BankDB"
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_TRUSTED_CONNECTION: bool = True
    DB_ENCRYPT: bool = False
    DB_TRUST_SERVER_CERTIFICATE: bool = True

    # App
    APP_NAME: str = "Bank-2PC"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    DEBUG: bool = True

    # CORS
    CORS_ALLOW_ORIGINS: str = "*"
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = False

    LOCK_TIMEOUT: int = 30

    @staticmethod
    def _parse_csv_or_json_list(raw: str) -> list[str]:
        value = (raw or "").strip()
        if not value:
            return []

        # Support JSON list in env, e.g. ["http://localhost:3000", "http://localhost:8080"]
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass

        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def cors_allow_origins_list(self) -> list[str]:
        parsed = self._parse_csv_or_json_list(self.CORS_ALLOW_ORIGINS)
        return parsed or ["*"]

    @property
    def cors_allow_methods_list(self) -> list[str]:
        parsed = self._parse_csv_or_json_list(self.CORS_ALLOW_METHODS)
        return parsed or ["*"]

    @property
    def cors_allow_headers_list(self) -> list[str]:
        parsed = self._parse_csv_or_json_list(self.CORS_ALLOW_HEADERS)
        return parsed or ["*"]

    @property
    def _driver_query(self) -> str:
        return self.DB_DRIVER.replace(" ", "+")

    @property
    def DATABASE_URL(self) -> str:
        encrypt = "yes" if self.DB_ENCRYPT else "no"
        trust_cert = "yes" if self.DB_TRUST_SERVER_CERTIFICATE else "no"

        if self.DB_TRUSTED_CONNECTION:
            return (
                f"mssql+pyodbc://@{self.DB_SERVER}/{self.DB_NAME}?"
                f"driver={self._driver_query}&"
                "Trusted_Connection=yes&"
                f"Encrypt={encrypt}&TrustServerCertificate={trust_cert}"
            )

        username = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"mssql+pyodbc://{username}:{password}@{self.DB_SERVER}/{self.DB_NAME}?"
            f"driver={self._driver_query}&"
            f"Encrypt={encrypt}&TrustServerCertificate={trust_cert}"
        )

    @property
    def MASTER_DATABASE_URL(self) -> str:
        encrypt = "yes" if self.DB_ENCRYPT else "no"
        trust_cert = "yes" if self.DB_TRUST_SERVER_CERTIFICATE else "no"

        if self.DB_TRUSTED_CONNECTION:
            return (
                f"mssql+pyodbc://@{self.DB_SERVER}/master?"
                f"driver={self._driver_query}&"
                "Trusted_Connection=yes&"
                f"Encrypt={encrypt}&TrustServerCertificate={trust_cert}"
            )

        username = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"mssql+pyodbc://{username}:{password}@{self.DB_SERVER}/master?"
            f"driver={self._driver_query}&"
            f"Encrypt={encrypt}&TrustServerCertificate={trust_cert}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
