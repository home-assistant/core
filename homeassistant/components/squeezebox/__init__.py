"""The Squeezebox integration."""

from asyncio import timeout
from dataclasses import dataclass
import logging

from pysqueezebox import Server

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
    format_mac,
)

from .const import (
    CONF_HTTPS,
    DISCOVERY_TASK,
    DOMAIN,
    MANUFACTURER,
    SERVER_MODEL,
    STATUS_API_TIMEOUT,
    STATUS_QUERY_LIBRARYNAME,
    STATUS_QUERY_MAC,
    STATUS_QUERY_UUID,
    STATUS_QUERY_VERSION,
)
from .coordinator import LMSStatusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
]


@dataclass
class SqueezeboxData:
    """SqueezeboxData data class."""

    coordinator: LMSStatusDataUpdateCoordinator
    server: Server


type SqueezeboxConfigEntry = ConfigEntry[SqueezeboxData]


async def async_setup_entry(hass: HomeAssistant, entry: SqueezeboxConfigEntry) -> bool:
    """Set up an LMS Server from a config entry."""
    config = entry.data
    session = async_get_clientsession(hass)
    _LOGGER.debug(
        "Reached async_setup_entry for host=%s(%s)", config[CONF_HOST], entry.entry_id
    )

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    https = config.get(CONF_HTTPS, False)
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    lms = Server(session, host, port, username, password, https=https)
    _LOGGER.debug("LMS object for %s", lms)

    try:
        async with timeout(STATUS_API_TIMEOUT):
            status = await lms.async_query(
                "serverstatus", "-", "-", "prefs:libraryname"
            )
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error communicating config not read for {host}"
        ) from err

    if not status:
        raise ConfigEntryNotReady(f"Error Config Not read for {host}")
    _LOGGER.debug("LMS Status for setup  = %s", status)

    lms.uuid = status[STATUS_QUERY_UUID]
    _LOGGER.debug("LMS %s = '%s' with uuid = %s ", lms.name, host, lms.uuid)
    lms.name = (
        (STATUS_QUERY_LIBRARYNAME in status and status[STATUS_QUERY_LIBRARYNAME])
        and status[STATUS_QUERY_LIBRARYNAME]
        or host
    )
    version = STATUS_QUERY_VERSION in status and status[STATUS_QUERY_VERSION] or None
    # mac can be missing
    mac_connect = (
        {(CONNECTION_NETWORK_MAC, format_mac(status[STATUS_QUERY_MAC]))}
        if STATUS_QUERY_MAC in status
        else None
    )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, lms.uuid)},
        name=lms.name,
        manufacturer=MANUFACTURER,
        model=SERVER_MODEL,
        sw_version=version,
        entry_type=DeviceEntryType.SERVICE,
        connections=mac_connect,
    )
    _LOGGER.debug("LMS Device %s", device)

    coordinator = LMSStatusDataUpdateCoordinator(hass, lms)

    entry.runtime_data = SqueezeboxData(
        coordinator=coordinator,
        server=lms,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SqueezeboxConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop player discovery task for this config entry.
    _LOGGER.debug(
        "Reached async_unload_entry for LMS=%s(%s)",
        entry.runtime_data.server.name or "Unknown",
        entry.entry_id,
    )

    # Stop server discovery task if this is the last config entry.
    current_entries = hass.config_entries.async_entries(DOMAIN)
    if len(current_entries) == 1 and current_entries[0] == entry:
        _LOGGER.debug("Stopping server discovery task")
        hass.data[DOMAIN][DISCOVERY_TASK].cancel()
        hass.data[DOMAIN].pop(DISCOVERY_TASK)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
