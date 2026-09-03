"""LANBON LOIP integration setup. I/O goes only through aiolanbon."""

from dataclasses import dataclass
import logging

from aiolanbon import LanbonClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_GATEWAY_ID, CONF_SCHEME
from .coordinator import LanbonCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]


@dataclass
class LanbonRuntimeData:
    """Runtime objects for a config entry."""

    client: LanbonClient
    coordinator: LanbonCoordinator


type LanbonConfigEntry = ConfigEntry[LanbonRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    """Set up LANBON from a config entry."""
    host = entry.data[CONF_HOST]
    port = int(entry.data.get(CONF_PORT, 8765))
    token = entry.data[CONF_TOKEN]
    scheme = entry.data.get(CONF_SCHEME, "http")
    session = async_get_clientsession(hass)
    client = LanbonClient(host, port, token, session, scheme=scheme)
    coordinator = LanbonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LanbonRuntimeData(client=client, coordinator=coordinator)
    entry.async_on_unload(coordinator.async_on_unload)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug(
        "LANBON LOIP setup host=%s gateway=%s",
        host,
        entry.data.get(CONF_GATEWAY_ID, ""),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
