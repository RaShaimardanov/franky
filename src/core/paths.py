from pathlib import Path, PurePath
from typing import Final

# Path to the root of project
ROOT_DIR: Final[Path] = Path(__file__).parent.parent.parent

LOGS_DIR = PurePath(ROOT_DIR / "logs/")
DATA_DIR = PurePath(ROOT_DIR / "data/")
LOCALES_DIR = PurePath(DATA_DIR / "locales/")
BROADCASTS_DIR = PurePath(DATA_DIR / "broadcasts/")
