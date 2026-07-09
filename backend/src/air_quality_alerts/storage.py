"""Persistencia liviana de sesiones/jobs de cálculo.

El backend usa SQLite por defecto para desarrollo local y PostgreSQL cuando se
configura DATABASE_URL. Esto permite que la página web consulte el progreso real
sin depender de memoria del proceso.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, Float, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.sql import insert, update

from air_quality_alerts.config import Settings

metadata = MetaData()

jobs_table = Table(
    "calculation_jobs",
    metadata,
    # UUID generado por la API. Se usa también como carpeta de artefactos.
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("status", String(32), nullable=False, default="queued"),
    Column("progress", Float, nullable=False, default=0.0),
    Column("current_step", String(160), nullable=False, default="En cola"),
    Column("message", Text, nullable=False, default=""),
    Column("request_payload", Text, nullable=False, default="{}"),
    Column("result_payload", Text, nullable=True),
    Column("events", Text, nullable=False, default="[]"),
    Column("error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class JobRepository:
    """Repositorio transaccional para sesiones de cálculo."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = _normalise_database_url(database_url or Settings.DATABASE_URL)
        connect_args = {"check_same_thread": False} if self.database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(self.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)

    def init_schema(self) -> None:
        metadata.create_all(self.engine)

    @contextmanager
    def _begin(self) -> Iterator[Any]:
        with self.engine.begin() as connection:
            yield connection

    def create_job(self, *, job_id: str, kind: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        event = _event("queued", 0, "Trabajo creado", "En cola", now)
        row = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0.0,
            "current_step": "En cola",
            "message": "Trabajo creado",
            "request_payload": _dump_json(request_payload),
            "result_payload": None,
            "events": _dump_json([event]),
            "error": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        with self._begin() as connection:
            connection.execute(insert(jobs_table).values(**row))
        return self.get_job(job_id) or {}

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        current_step: str | None = None,
        message: str | None = None,
        result_payload: dict[str, Any] | None = None,
        error: str | None = None,
        completed: bool = False,
        append_event: bool = True,
    ) -> dict[str, Any]:
        current = self.get_job(job_id)
        if not current:
            raise KeyError(f"No existe el job {job_id}")

        now = _utcnow()
        values: dict[str, Any] = {"updated_at": now}
        if status is not None:
            values["status"] = status
        if progress is not None:
            values["progress"] = float(max(0, min(progress, 100)))
        if current_step is not None:
            values["current_step"] = current_step[:160]
        if message is not None:
            values["message"] = message
        if result_payload is not None:
            values["result_payload"] = _dump_json(result_payload)
        if error is not None:
            values["error"] = error
        if completed:
            values["completed_at"] = now

        events = list(current.get("events") or [])
        if append_event:
            events.append(
                _event(
                    values.get("status", current.get("status", "running")),
                    values.get("progress", current.get("progress", 0)),
                    values.get("current_step", current.get("current_step", "Proceso")),
                    values.get("message", current.get("message", "")),
                    now,
                )
            )
            values["events"] = _dump_json(events[-80:])

        with self._begin() as connection:
            connection.execute(update(jobs_table).where(jobs_table.c.id == job_id).values(**values))
        return self.get_job(job_id) or {}

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(jobs_table).where(jobs_table.c.id == job_id)).mappings().first()
        return _row_to_dict(row) if row else None

    def list_jobs(self, limit: int = 25) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        statement = select(jobs_table).order_by(jobs_table.c.created_at.desc()).limit(limit)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["request_payload"] = _load_json(data.get("request_payload"), {})
    data["result_payload"] = _load_json(data.get("result_payload"), None)
    data["events"] = _load_json(data.get("events"), [])
    for field in ("created_at", "updated_at", "completed_at"):
        value = data.get(field)
        if isinstance(value, datetime):
            data[field] = value.isoformat()
    return data


def _event(status: str, progress: float, step: str, message: str, timestamp: datetime) -> dict[str, Any]:
    return {
        "timestamp": timestamp.isoformat(),
        "status": status,
        "progress": round(float(progress), 2),
        "step": step,
        "message": message,
    }


def _dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _load_json(payload: str | None, default: Any) -> Any:
    if not payload:
        return default
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return default


def _utcnow() -> datetime:
    return datetime.now(UTC)
