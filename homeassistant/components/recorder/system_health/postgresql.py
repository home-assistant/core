"""Provide info to system health for postgresql."""
from __future__ import annotations

from typing import cast

from sqlalchemy import text
from sqlalchemy.orm.session import Session


def db_size_query(session: Session, database_name: str) -> str:
    """Get the mysql database size."""
    return cast(
        str,
        session.execute(
            text("select pg_database_size(:database_name);"),
            {"database_name": database_name},
        ).first()[0],
    )
