from functools import lru_cache
from pydantic import BaseModel
import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()


def default_sqlite_url() -> str:
    base = os.getenv("LOCALAPPDATA") or os.getenv("TMP") or os.getcwd()
    db_dir = Path(base) / "DBAChangeOps"
    return f"sqlite:///{db_dir.as_posix()}/changeops.db"


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL") or default_sqlite_url()
    llm_base_url: str = os.getenv(
        "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "qwen-plus")
    app_env: str = os.getenv("APP_ENV", "development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
