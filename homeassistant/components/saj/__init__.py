"""The saj component."""

from typing import Any

import pysaj

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONNECTION_TYPES
from .coordinator import SAJConfigEntry, SAJDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Set up SAJ from a config entry."""
    host = entry.data[CONF_HOST]
    connection_type = entry.data[CONF_TYPE]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    kwargs: dict[str, Any] = {}
    wifi = connection_type == CONNECTION_TYPES[1]
    if wifi:
        kwargs["wifi"] = True
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password

    saj = pysaj.SAJ(host, **kwargs)
    sensor_def = pysaj.Sensors(wifi)

    coordinator = SAJDataUpdateCoordinator(hass, entry, saj, sensor_def, wifi=wifi)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
