"""Provide info to system health for sqlite."""
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
                "SELECT page_count * page_size as size "
                "FROM pragma_page_count(), pragma_page_size();"
            )
        ).first()[0],
    )
