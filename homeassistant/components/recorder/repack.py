"""Purge repack helper."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


def repack_database(instance: Recorder) -> None:
    """Repack based on engine type."""
    assert instance.engine is not None
    dialect_name = instance.engine.dialect.name

    # Execute sqlite command to free up space on disk
    if dialect_name == "sqlite":
        _LOGGER.debug("Vacuuming SQL DB to free space")
        instance.engine.execute("VACUUM")
        return

    # Execute postgresql vacuum command to free up space on disk
    if dialect_name == "postgresql":
        _LOGGER.debug("Vacuuming SQL DB to free space")
        with instance.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute("VACUUM")
        return

    # Optimize mysql / mariadb tables to free up space on disk
    if dialect_name == "mysql":
        _LOGGER.debug("Optimizing SQL DB to free space")
        instance.engine.execute("OPTIMIZE TABLE states, events, recorder_runs")
        return
