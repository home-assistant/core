"""Models for the database in the Recorder."""

from __future__ import annotations

from dataclasses import dataclass

from awesomeversion import AwesomeVersion

from ..const import SupportedDialect


class UnsupportedDialect(Exception):
    """The dialect or its version is not supported."""


@dataclass
class DatabaseEngine:
    """Properties of the database engine."""

    dialect: SupportedDialect
    max_bind_vars: int
    version: AwesomeVersion | None
