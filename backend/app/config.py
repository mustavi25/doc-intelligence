from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "docintel"
    upload_dir: str = "../data/uploads"
    anthropic_api_key: str = ""
    extraction_model: str = "claude-sonnet-4-6"
    tesseract_cmd: str = "tesseract"
    ocr_engine: str = "auto"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


settings = Settings()
