"""Provide info to system health for mysql."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm.session import Session


def db_size_bytes(session: Session, database_name: str) -> float:
    """Get the mysql database size."""
    return float(
        session.execute(
            text(
                "SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH), 2) "
                "FROM information_schema.TABLES WHERE "
                "TABLE_SCHEMA=:database_name"
            ),
            {"database_name": database_name},
        ).first()[0]
    )
