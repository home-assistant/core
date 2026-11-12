"""The Voltie Charger integration."""

from voltie import VoltieCharger

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    VoltieChargerConfigEntry,
    VoltieDataUpdateCoordinator,
    VoltieRuntimeData,
)

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: VoltieChargerConfigEntry
) -> None:
    """Set up a Voltie charger from a config entry."""
    charger = VoltieCharger(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        # Entries without authentication may hold empty credentials
        username=entry.data.get(CONF_USERNAME) or None,
        password=entry.data.get(CONF_PASSWORD) or None,
        session=async_get_clientsession(hass),
    )

    data_coordinator = VoltieDataUpdateCoordinator(hass, entry, charger)
    await data_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = VoltieRuntimeData(
        charger=charger,
        data_coordinator=data_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: VoltieChargerConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
