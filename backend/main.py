import json
import math
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.charts.trend import get_trend_figures
from app.config.settings import IMPORT_DIR, MAPPING_DIR, ensure_runtime_dirs
from app.data.db import get_connection, get_latest_snapshot_id
from app.data.etl import process_file
from app.data.kpi import build_where_clause, get_filter_options, get_summary_metrics

ensure_runtime_dirs()


class FilterRequest(BaseModel):
    snapshot_id: str
    filters: Dict[str, List[str]]


def create_app() -> FastAPI:
    app = FastAPI(title="AR Nexus API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/ping")
    def ping() -> dict:
        return {"status": "ok"}

    @app.get("/api/snapshot")
    def get_snapshot() -> dict:
        return {"snapshot_id": get_latest_snapshot_id()}

    @app.post("/api/upload")
    async def upload_files(files: List[UploadFile] = File(...)) -> dict:
        success_count = 0
        errors: List[str] = []

        for file in files:
            if file.filename.lower().startswith("assign_ar_team"):
                filepath = MAPPING_DIR / file.filename
                with filepath.open("wb") as buffer:
                    buffer.write(await file.read())
                success_count += 1
                continue

            filepath = IMPORT_DIR / file.filename
            with filepath.open("wb") as buffer:
                buffer.write(await file.read())

            result = process_file(str(filepath))
            if result["success"]:
                success_count += 1
            else:
                errors.append(f"{file.filename}: {result['message']}")

        return {"success": success_count > 0, "success_count": success_count, "errors": errors}

    @app.post("/api/filters")
    def get_filters(req: FilterRequest) -> dict:
        return get_filter_options(req.snapshot_id, req.filters)

    @app.post("/api/metrics")
    def get_metrics(req: FilterRequest) -> dict:
        metrics = get_summary_metrics(req.snapshot_id, req.filters)
        return _sanitize_metrics(metrics)

    @app.post("/api/trend")
    def get_trend(req: FilterRequest) -> list:
        figures = get_trend_figures(req.snapshot_id, req.filters)
        return [
            {
                "title": chart.get("title", ""),
                "fig_json": json.loads(chart["fig"].to_json()),
            }
            for chart in figures
        ]

    @app.post("/api/data")
    def get_data(req: FilterRequest) -> list:
        conn = get_connection()
        try:
            where_sql, params = build_where_clause(req.filters, req.snapshot_id)
            df = conn.execute(f"SELECT * FROM fact_ar {where_sql} LIMIT 1000", params).fetchdf()
            if df.empty:
                return []

            cols_to_drop = [c for c in df.columns if c.lower() in {"unnamed: 0", "unnamed_0", "snapshot_id"}]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

            return df.fillna("").to_dict(orient="records")
        except Exception as exc:
            print(f"Data error: {exc}")
            return []
        finally:
            conn.close()

    return app


def _sanitize_metrics(metrics: dict) -> dict:
    sanitized = dict(metrics)
    for key, value in sanitized.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            sanitized[key] = 0.0
    return sanitized


app = create_app()
