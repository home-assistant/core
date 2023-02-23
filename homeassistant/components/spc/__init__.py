"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""
import logging

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.area import Area
from pyspcwebgw.zone import Zone
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_URL,
    CONF_WS_URL,
    DOMAIN,
    SIGNAL_UPDATE_ALARM,
    SIGNAL_UPDATE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_WS_URL): cv.string,
                vol.Required(CONF_API_URL): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SPC component."""

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def _async_update_callback(hass, spc_object):
    if isinstance(spc_object, Area):
        async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(spc_object.id))
    elif isinstance(spc_object, Zone):
        async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(spc_object.id))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SPC from a config entry."""
    config = entry.data

    spc = SpcWebGateway(
        loop=hass.loop,
        session=async_create_clientsession(hass),
        api_url=config.get(CONF_API_URL),
        ws_url=config.get(CONF_WS_URL),
        async_callback=lambda spc_object: _async_update_callback(hass, spc_object),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = spc

    if not await spc.async_load_parameters():
        raise ConfigEntryNotReady("Failed to load area/zone information from SPC")

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, spc.info["sn"])},
        manufacturer="Vanderbilt",
        name=spc.info["sn"],
        model=spc.info["type"],
        sw_version=spc.info["version"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # start listening for incoming events over websocket
    spc.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id].stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
