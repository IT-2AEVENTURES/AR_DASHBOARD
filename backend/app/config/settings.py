from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_PATH = str(PROJECT_ROOT / "ar_dashboard.duckdb")
DATA_DIR = BACKEND_DIR / "data"
IMPORT_DIR = DATA_DIR / "imports"
MAPPING_DIR = DATA_DIR / "mapping"
ARCHIVE_DIR = DATA_DIR / "archive"
EXPORT_DIR = BACKEND_DIR / "exports"


def ensure_runtime_dirs() -> None:
    for directory in (DATA_DIR, IMPORT_DIR, MAPPING_DIR, ARCHIVE_DIR, EXPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
