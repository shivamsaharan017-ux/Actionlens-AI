from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./actionlens.db"
    jwt_secret: str = "local-demo-secret-change-this-before-deploying"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = "google/gemma-4-E2B-it"
    max_upload_mb: int = 10
    storage_dir: str = "./storage"
    frontend_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
