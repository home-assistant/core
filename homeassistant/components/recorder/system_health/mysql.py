"""Provide info to system health for mysql."""
from __future__ import annotations

from typing import cast

from sqlalchemy import text
from sqlalchemy.orm.session import Session


def db_size_query(session: Session, database_name: str) -> str:
    """Get the mysql database size."""
    return cast(
        str,
        session.execute(
            text(
                "SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA=:database_name"
            ),
            {"database_name": database_name},
        ).first()[0],
    )
