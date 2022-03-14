"""Backup helpers."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from homeassistant.components.backup.manager import BackupManager


@callback
def register_backup_callback(
    hass: HomeAssistant,
    *,
    finish: Awaitable | None = None,
    start: Awaitable | None = None,
) -> None:
    """Register callbacks to be called when a backup starts or finishes."""
    manager: BackupManager | None = hass.data.get("backup")
    if manager is not None:
        manager.register_backup_callback(finish=finish, start=start)
