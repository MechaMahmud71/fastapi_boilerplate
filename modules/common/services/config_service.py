import os
from dotenv import load_dotenv

load_dotenv()  # load .env variables

class ConfigService:
    def get(self, key: str) -> str:
        return os.getenv(key)

# create a singleton instance to use throughout your project
config_service = ConfigService()
