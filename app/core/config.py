from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareShift"
    environment: str = "dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()