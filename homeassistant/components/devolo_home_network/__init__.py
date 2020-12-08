"""The devolo Home Network integration."""
import asyncio

from devolo_plc_api.device import Device
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the devolo Home Network component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up devolo Home Network from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    conf = entry.data
    hass.data.setdefault(DOMAIN, {})

    zeroconf_instance = await zeroconf.async_get_instance(hass)
    # TODO Reuse zeroconf data (detection code needed)
    device = Device(ip=conf[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance)
    device.password = conf.get(CONF_PASSWORD) or ""

    hass.data[DOMAIN][entry.entry_id] = device
    await device.async_connect()
    # This should be done in validate_input
    entry.title = device.hostname.split(".")[0]

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # TODO Listen to EVENT_HOMEASSISTANT_STOP

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
        await hass.data[DOMAIN][entry.entry_id].async_disconnect()
        # TODO Remove listener
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
