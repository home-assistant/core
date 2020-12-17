"""The devolo Home Network integration."""
import asyncio
import logging

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the devolo Home Network component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up devolo Home Network from a config entry."""
    conf = entry.data
    hass.data.setdefault(DOMAIN, {})

    zeroconf_instance = await zeroconf.async_get_instance(hass)
    async_client = get_async_client(hass)

    try:
        device = Device(ip=conf[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance)
        await device.async_connect(session_instance=async_client)
    except DeviceNotFound as error:
        _LOGGER.warning("Unable to connect to %s.", conf[CONF_IP_ADDRESS])
        raise ConfigEntryNotReady from error

    hass.data[DOMAIN][entry.entry_id] = {"device": device, "listener": None}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def disconnect(event):
        await hass.data[DOMAIN][entry.entry_id]["device"].async_disconnect()

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    hass.data[DOMAIN][entry.entry_id]["listener"] = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, disconnect
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id]["device"].async_disconnect()
        hass.data[DOMAIN][entry.entry_id]["listener"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
