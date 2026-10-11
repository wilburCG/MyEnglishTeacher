from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://met:met_dev_pwd@localhost:5435/met"
    secret_key: str = "met-dev-secret-change-me"
    token_expire_days: int = 30

    # 火山方舟 ARK（M3 启用）
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "ark-code-latest"

    # 火山语音评测（M5 启用）
    volc_speech_appid: str = ""
    volc_speech_token: str = ""

    media_dir: str = "/data"
    daily_dialogue_turns: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
