import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_SUB_PRICE_30: str = os.getenv("STRIPE_SUB_PRICE_30", "")
    STRIPE_SUB_PRICE_100: str = os.getenv("STRIPE_SUB_PRICE_100", "")
    STRIPE_SUB_PRICE_UNLIMITED: str = os.getenv("STRIPE_SUB_PRICE_UNLIMITED", "")
    FREE_PHOTOS_LIMIT: int = int(os.getenv("FREE_PHOTOS_LIMIT", "3"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))


settings = Settings()
