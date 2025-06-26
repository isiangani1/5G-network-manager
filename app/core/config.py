"""
Configuration settings for the 5G Slice Manager application.

This module loads configuration from environment variables with sensible defaults.
"""

from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Application settings
    APP_NAME: str = "5G Slice Manager"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    WEB_CONCURRENCY: int = 1
    
    # Security settings
    SECRET_KEY: str = "your-secure-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database settings
    DB_TYPE: str = "postgresql"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/5g_slice_manager"
    
    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """Get the async database URL, ensuring it uses the correct driver and removes unsupported parameters."""
        if self.DATABASE_URL.startswith('postgresql://'):
            # Remove any query parameters that asyncpg doesn't support
            base_url = self.DATABASE_URL.split('?')[0]
            if '+asyncpg' not in base_url:
                base_url = base_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
            return base_url
        return self.DATABASE_URL
        
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Get the sync database URL, ensuring it doesn't use async driver."""
        return self.DATABASE_URL.replace('+asyncpg', '')
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # NS3 Simulation (optional)
    NS3_SIMULATION_ENABLED: bool = False
    NS3_API_URL: str = "http://localhost:3000"
    
    # WebSocket settings
    WEBSOCKET_PING_INTERVAL: int = 30
    WEBSOCKET_PING_TIMEOUT: int = 60
    
    # Security headers
    SECURE_COOKIES: bool = not DEBUG
    SESSION_COOKIE_NAME: str = "session"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = not DEBUG
    SESSION_COOKIE_SAMESITE: str = "lax"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_prefix="APP_",  # Use APP_ prefix for all environment variables
        extra="ignore"  # Ignore extra environment variables
    )
    
    @field_validator("SECRET_KEY")
    def validate_secret_key(cls, v: str) -> str:
        if v == "your-secure-secret-key-here":
            import warnings
            warnings.warn(
                "Using default SECRET_KEY. This is not secure for production! "
                "Please set APP_SECRET_KEY environment variable.",
                UserWarning
            )
        return v
    
    @field_validator("CORS_ORIGINS")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError("CORS_ORIGINS must be a string or a list of strings")
    
    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {', '.join(valid_levels)}")
        return v


# Create settings instance
settings = Settings()
