"""DayBetter Services integration setup."""

from __future__ import annotations

from datetime import timedelta

from daybetter_python import DayBetterClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, DayBetterConfigEntry, DayBetterRuntimeData
from .coordinator import DayBetterCoordinator

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(seconds=300)


async def async_setup_entry(hass: HomeAssistant, entry: DayBetterConfigEntry) -> bool:
    """Set up DayBetter from a config entry."""
    client = DayBetterClient(token=entry.data[CONF_TOKEN])

    coordinator = DayBetterCoordinator(
        hass,
        entry,
        client,
        SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = DayBetterRuntimeData(coordinator=coordinator, client=client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DayBetterConfigEntry) -> bool:
    """Unload DayBetter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
