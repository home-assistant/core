"""Provide info to system health for sqlite."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm.session import Session


def db_size_bytes(session: Session, database_name: str) -> float:
    """Get the mysql database size."""
    return float(
        session.execute(
            text(
                "SELECT page_count * page_size as size "
                "FROM pragma_page_count(), pragma_page_size();"
            )
        ).first()[0]
    )
