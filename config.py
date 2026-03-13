from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_token: str
    telegram_secret_token: str
    anthropic_api_key: str
    notion_api_key: str
    notion_scribble_db_id: str
    notion_project_db_id: str

    class Config:
        env_file = ".env"


settings = Settings()
