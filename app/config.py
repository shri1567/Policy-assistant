from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str
    similarity_threshold: float = 0.55
    default_top_k: int = 4
    embedding_model: str = "text-embedding-004"
    generation_model: str = "gemini-3.6-flash"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()