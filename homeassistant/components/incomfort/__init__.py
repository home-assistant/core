"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

from incomfortclient import Gateway as InComfortGateway

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import InComfortConfigEntry, InComfortDataCoordinator

PLATFORMS = (
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
)

INTEGRATION_TITLE = "Intergas InComfort/Intouch Lan2RF gateway"


async def async_setup_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Set up a config entry."""

    credentials = dict(entry.data)
    hostname = credentials.pop(CONF_HOST)
    client = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )

    coordinator = InComfortDataCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
