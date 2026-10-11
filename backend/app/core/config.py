from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://met:met_dev_pwd@localhost:5435/met"

    # LLM: 火山方舟 ARK（与 Mose 当前相同的模型 / agent-plan 端点）
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "ark-code-latest"

    # 语音评测（火山，M5 启用）
    volc_speech_appid: str = ""
    volc_speech_token: str = ""

    # 限额
    daily_dialogue_turns: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
