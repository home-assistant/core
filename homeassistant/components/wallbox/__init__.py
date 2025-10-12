"""The Wallbox integration."""

from __future__ import annotations

from datetime import datetime

from wallbox import Wallbox

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CHARGER_JWT_REFRESH_TOKEN,
    CHARGER_JWT_REFRESH_TTL,
    CHARGER_JWT_TOKEN,
    CHARGER_JWT_TTL,
    UPDATE_INTERVAL,
)
from .coordinator import WallboxConfigEntry, WallboxCoordinator

PLATFORMS = [
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: WallboxConfigEntry) -> bool:
    """Set up Wallbox from a config entry."""
    wallbox = Wallbox(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        jwtTokenDrift=UPDATE_INTERVAL,
    )

    if entry.options.get(CHARGER_JWT_TOKEN) and (
        entry.options.get(CHARGER_JWT_TTL, 0) / 1000
    ) > datetime.timestamp(datetime.now()):
        wallbox.jwtToken = entry.options.get(CHARGER_JWT_TOKEN)
        wallbox.jwtRefreshToken = entry.options.get(CHARGER_JWT_REFRESH_TOKEN)
        wallbox.jwtTokenTtl = entry.options.get(CHARGER_JWT_TTL)
        wallbox.jwtRefreshTokenTtl = entry.options.get(CHARGER_JWT_REFRESH_TTL)
        wallbox.headers["Authorization"] = (
            f"Bearer {entry.options.get(CHARGER_JWT_TOKEN)}"
        )

        hass.config_entries.async_update_entry(entry, options={})

    wallbox_coordinator = WallboxCoordinator(hass, entry, wallbox)
    await wallbox_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = wallbox_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WallboxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
