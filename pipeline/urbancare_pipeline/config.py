import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("URBANCARE_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
BRONZE = DATA_DIR / "bronze"
SILVER = DATA_DIR / "silver"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
