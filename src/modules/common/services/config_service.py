import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()  # load .env variables

TRUTHY = {"1", "true", "yes", "on"}


class ConfigService:
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        value = os.getenv(key)
        return default if value is None or value == "" else value

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = os.getenv(key)
        if value is None or value == "":
            return default
        return value.strip().lower() in TRUTHY

    def get_int(self, key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None or value == "":
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_list(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        """Comma-separated env var -> list of trimmed values."""
        value = os.getenv(key)
        if value is None or value.strip() == "":
            return list(default or [])
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def env(self) -> str:
        return self.get("APP_ENV", "development").lower()

    @property
    def is_production(self) -> bool:
        return self.env == "production"


# create a singleton instance to use throughout your project
config_service = ConfigService()
