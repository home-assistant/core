"""The devolo Home Network integration."""
import logging

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up devolo Home Network from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    zeroconf_instance = await zeroconf.async_get_instance(hass)
    async_client = get_async_client(hass)

    try:
        device = Device(
            ip=entry.data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance
        )
        await device.async_connect(session_instance=async_client)
    except DeviceNotFound as error:
        _LOGGER.warning("Unable to connect to %s", entry.data[CONF_IP_ADDRESS])
        raise ConfigEntryNotReady from error

    hass.data[DOMAIN][entry.entry_id] = device

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def disconnect(event: Event) -> None:
        await hass.data[DOMAIN][entry.entry_id]["device"].async_disconnect()

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id].async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
