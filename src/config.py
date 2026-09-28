import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    START_URL: str = os.getenv("START_URL", "https://iditelesombase.org/")

settings = Settings()