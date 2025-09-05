"""The Ubiquiti airOS integration."""

from __future__ import annotations

from airos.airos8 import AirOS8

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AirOSConfigEntry, AirOSDataUpdateCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Set up Ubiquiti airOS from a config entry."""

    # By default airOS 8 comes with self-signed SSL certificates,
    # with no option in the web UI to change or upload a custom certificate.
    session = async_get_clientsession(hass, verify_ssl=False)

    airos_device = AirOS8(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    coordinator = AirOSDataUpdateCoordinator(hass, entry, airos_device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
