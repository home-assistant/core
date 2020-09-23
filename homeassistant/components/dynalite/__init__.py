"""Support for the Dynalite networks."""

import asyncio
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .bridge_schema import BRIDGE_SCHEMA
from .const import (
    ATTR_AREA,
    ATTR_CHANNEL,
    ATTR_HOST,
    CONF_BRIDGES,
    DOMAIN,
    ENTITY_PLATFORMS,
    LOGGER,
    SERVICE_REQUEST_AREA_PRESET,
    SERVICE_REQUEST_CHANNEL_LEVEL,
)
from .websocket_api import async_register_api

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_BRIDGES): vol.All(cv.ensure_list, [BRIDGE_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the Dynalite platform."""
    conf = config.get(DOMAIN)
    LOGGER.debug("Setting up dynalite component config = %s", conf)

    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}

    # User has configured bridges
    if CONF_BRIDGES in conf:
        bridges = conf[CONF_BRIDGES]
        for bridge_conf in bridges:
            host = bridge_conf[CONF_HOST]
            LOGGER.debug(
                "Starting config entry flow host=%s conf=%s", host, bridge_conf
            )
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=bridge_conf,
                )
            )

    async def dynalite_service(service_call: ServiceCall):
        data = service_call.data
        host = data.get(ATTR_HOST, "")
        bridges = []
        for cur_bridge in hass.data[DOMAIN].values():
            if not host or cur_bridge.host == host:
                bridges.append(cur_bridge)
        LOGGER.debug("Selected bridged for service call: %s", bridges)
        if service_call.service == SERVICE_REQUEST_AREA_PRESET:
            bridge_attr = "request_area_preset"
        elif service_call.service == SERVICE_REQUEST_CHANNEL_LEVEL:
            bridge_attr = "request_channel_level"
        for bridge in bridges:
            getattr(bridge.dynalite_devices, bridge_attr)(
                data[ATTR_AREA], data.get(ATTR_CHANNEL)
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_AREA_PRESET,
        dynalite_service,
        vol.Schema(
            {
                vol.Optional(ATTR_HOST): cv.string,
                vol.Required(ATTR_AREA): int,
                vol.Optional(ATTR_CHANNEL): int,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_CHANNEL_LEVEL,
        dynalite_service,
        vol.Schema(
            {
                vol.Optional(ATTR_HOST): cv.string,
                vol.Required(ATTR_AREA): int,
                vol.Required(ATTR_CHANNEL): int,
            }
        ),
    )

    async_register_api(hass)

    return True


async def async_entry_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry since the data has changed."""
    LOGGER.debug("Reconfiguring entry %s", entry.data)
    bridge = hass.data[DOMAIN][entry.entry_id]
    bridge.reload_config(entry.data)
    LOGGER.debug("Reconfiguring entry finished %s", entry.data)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a bridge from a config entry."""
    LOGGER.debug("Setting up entry %s", entry.data)
    bridge = DynaliteBridge(hass, entry.data)
    # need to do it before the listener
    hass.data[DOMAIN][entry.entry_id] = bridge
    entry.add_update_listener(async_entry_changed)
    if not await bridge.async_setup():
        LOGGER.error("Could not set up bridge for entry %s", entry.data)
        hass.data[DOMAIN][entry.entry_id] = None
        raise ConfigEntryNotReady
    for platform in ENTITY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.data)
    hass.data[DOMAIN].pop(entry.entry_id)
    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in ENTITY_PLATFORMS
    ]
    results = await asyncio.gather(*tasks)
    return False not in results
