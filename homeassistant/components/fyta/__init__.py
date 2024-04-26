"""Initialization of FYTA integration."""

from __future__ import annotations

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from fyta_cli.fyta_connector import FytaConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FytaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Fyta integration."""
    tz: str = hass.config.time_zone

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    access_token: str = entry.data.get("access_token", "")
    expiration: datetime | None = (
        datetime.fromisoformat(entry.data.get("expiration", "")).astimezone(
            ZoneInfo(tz)
        )
        if "expiration" in entry.data
        else None
    )

    fyta = FytaConnector(username, password, access_token, expiration, tz)

    coordinator = FytaCoordinator(hass, fyta)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Fyta entity."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
