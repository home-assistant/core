"""The xbox integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import (
    XboxConfigEntry,
    XboxConsolesCoordinator,
    XboxCoordinators,
    XboxUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Set up xbox from a config entry."""

    coordinator = XboxUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    consoles = XboxConsolesCoordinator(hass, entry, coordinator)

    entry.runtime_data = XboxCoordinators(coordinator, consoles)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_migrate_config_entry(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: XboxConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_config_entry(
    hass: HomeAssistant, entry: XboxConfigEntry
) -> bool:
    """Migrate config entry.

    Migration requires runtime data
    """
    coordinator = entry.runtime_data.status

    if entry.version == 1 and entry.minor_version < 2:
        # Migrate unique_id from `xbox` to account xuid and
        # change generic entry name to user's gamertag
        xuid = coordinator.client.xuid
        gamertag = coordinator.data.presence[xuid].gamertag

        hass.config_entries.async_update_entry(
            entry,
            unique_id=xuid,
            title=(gamertag if entry.title == "Home Assistant Cloud" else entry.title),
            minor_version=2,
        )
    if entry.version == 1 and entry.minor_version < 3:
        # Migrate favorite friends to friend subentries
        dev_reg = dr.async_get(hass)
        for friend in coordinator.data.presence.values():
            if not friend.is_favorite:
                continue
            subentry = ConfigSubentry(
                subentry_type="friend",
                title=friend.gamertag,
                unique_id=friend.xuid,
                data={},  # type: ignore[arg-type]
            )
            hass.config_entries.async_add_subentry(entry, subentry)

            if device := dev_reg.async_get_device({(DOMAIN, friend.xuid)}):
                dev_reg.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                    add_config_subentry_id=subentry.subentry_id,
                    add_config_entry_id=entry.entry_id,
                )
        hass.config_entries.async_update_entry(entry, minor_version=3)
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return True
