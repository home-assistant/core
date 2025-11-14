"""DayBetter Services integration setup."""

from __future__ import annotations

from datetime import timedelta

from daybetter_python import DayBetterClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TOKEN, DOMAIN, DayBetterConfigEntry, DayBetterRuntimeData
from .coordinator import DayBetterCoordinator

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DayBetterConfigEntry) -> bool:
    """Set up DayBetter from a config entry."""
    client = DayBetterClient(token=entry.data[CONF_TOKEN])

    coordinator = DayBetterCoordinator(
        hass,
        client,
        SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    runtime_data = DayBetterRuntimeData(coordinator=coordinator, client=client)
    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DayBetterConfigEntry) -> bool:
    """Unload DayBetter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
