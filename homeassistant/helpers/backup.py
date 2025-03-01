"""Helpers for the backup integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.components.backup import (
        BackupManager,
        BackupPlatformEvent,
        ManagerStateEvent,
    )

DATA_BACKUP: HassKey[BackupData] = HassKey("backup_data")
DATA_MANAGER: HassKey[BackupManager] = HassKey("backup")


@dataclass(slots=True)
class BackupData:
    """Backup data stored in hass.data."""

    backup_event_subscriptions: list[Callable[[ManagerStateEvent], None]] = field(
        default_factory=list
    )
    backup_platform_event_subscriptions: list[Callable[[BackupPlatformEvent], None]] = (
        field(default_factory=list)
    )
    manager_ready: asyncio.Future[None] = field(default_factory=asyncio.Future)


@callback
def async_initialize_backup(hass: HomeAssistant) -> None:
    """Initialize backup data.

    This creates the BackupData instance stored in hass.data[DATA_BACKUP] and
    registers the basic backup websocket API which is used by frontend to subscribe
    to backup events.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.backup import basic_websocket

    hass.data[DATA_BACKUP] = BackupData()
    basic_websocket.async_register_websocket_handlers(hass)


async def async_get_manager(hass: HomeAssistant) -> BackupManager:
    """Get the backup manager instance.

    Raises HomeAssistantError if the backup integration is not available.
    """
    if DATA_BACKUP not in hass.data:
        raise HomeAssistantError("Backup integration is not available")

    await hass.data[DATA_BACKUP].manager_ready
    return hass.data[DATA_MANAGER]


@callback
def async_subscribe_events(
    hass: HomeAssistant,
    on_event: Callable[[ManagerStateEvent], None],
) -> Callable[[], None]:
    """Subscribe to backup events."""
    backup_event_subscriptions = hass.data[DATA_BACKUP].backup_event_subscriptions

    def remove_subscription() -> None:
        backup_event_subscriptions.remove(on_event)

    backup_event_subscriptions.append(on_event)
    return remove_subscription


@callback
def async_subscribe_platform_events(
    hass: HomeAssistant,
    on_event: Callable[[BackupPlatformEvent], None],
) -> Callable[[], None]:
    """Subscribe to backup platform events."""
    backup_platform_event_subscriptions = hass.data[
        DATA_BACKUP
    ].backup_platform_event_subscriptions

    def remove_subscription() -> None:
        backup_platform_event_subscriptions.remove(on_event)

    backup_platform_event_subscriptions.append(on_event)
    return remove_subscription
