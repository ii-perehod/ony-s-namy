import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "")
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
    FREE_PHOTOS_LIMIT: int = int(os.getenv("FREE_PHOTOS_LIMIT", "5"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))


settings = Settings()
