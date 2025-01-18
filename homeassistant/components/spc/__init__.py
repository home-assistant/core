"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""

from __future__ import annotations

import logging

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.area import Area
from pyspcwebgw.zone import Zone
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

CONF_WS_URL = "ws_url"
CONF_API_URL = "api_url"

DOMAIN = "spc"
DATA_API = "spc_api"

SIGNAL_UPDATE_ALARM = "spc_update_alarm_{}"
SIGNAL_UPDATE_SENSOR = "spc_update_sensor_{}"

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
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SPC from a config entry."""

    async def async_update_callback(spc_object: Area | Zone) -> None:
        if isinstance(spc_object, Area):
            async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(spc_object.id))
        elif isinstance(spc_object, Zone):
            async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(spc_object.id))

    session = aiohttp_client.async_get_clientsession(hass)

    spc = SpcWebGateway(
        loop=hass.loop,
        session=session,
        api_url=entry.data[CONF_API_URL],
        ws_url=entry.data[CONF_WS_URL],
        async_callback=async_update_callback,
    )

    if not await spc.async_load_parameters():
        _LOGGER.error("Failed to load area/zone information from SPC")
        return False

    hass.data[DOMAIN][entry.entry_id] = spc

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, spc.info["sn"])},
        manufacturer="Vanderbilt",
        name=spc.info["sn"],
        model=spc.info["type"],
        sw_version=spc.info["version"],
        configuration_url=f"http://{spc.ethernet['ip_address']}/",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    spc.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    spc = hass.data[DOMAIN][entry.entry_id]
    spc.stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
