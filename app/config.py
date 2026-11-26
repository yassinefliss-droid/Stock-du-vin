"""Configuration lue depuis les variables d'environnement / le fichier .env."""

from datetime import date
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./stock.db"
    secret_key: str = "dev-secret-a-changer"
    access_token_minutes: int = 480

    llm_provider: Literal["anthropic", "groq", "none"] = "none"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None

    # Permet de figer « aujourd'hui » pour l'assistant (utilisé par l'évaluation).
    assistant_today: date | None = None


settings = Settings()
