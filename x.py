from homeassistant.backports.enum import StrEnum


class SupportedDialect(StrEnum):
    """Supported dialects."""

    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"


SupportedDialect("bob")
