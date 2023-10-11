"""Provide info to system health for valid dialects."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm.session import Session

from ..const import SupportedDialect


def db_size_bytes(
    session: Session, database_name: str, dialect: SupportedDialect
) -> float | None:
    """Get the database size."""
    if dialect == SupportedDialect.MYSQL:
        size = session.execute(
            text(
                "SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH), 2) "
                "FROM information_schema.TABLES WHERE "
                "TABLE_SCHEMA=:database_name"
            ),
            {"database_name": database_name},
        ).scalar()

    elif dialect == SupportedDialect.POSTGRESQL:
        size = session.execute(
            text("select pg_database_size(:database_name);"),
            {"database_name": database_name},
        ).scalar()

    elif dialect == SupportedDialect.SQLITE:
        size = session.execute(
            text(
                "SELECT page_count * page_size as size "
                "FROM pragma_page_count(), pragma_page_size();"
            )
        ).scalar()

    if not size:
        return None
    return float(size)
