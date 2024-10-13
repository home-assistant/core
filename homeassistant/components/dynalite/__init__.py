"""Support for the Dynalite networks."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .const import (
    ATTR_AREA,
    ATTR_CHANNEL,
    ATTR_HOST,
    CONF_BRIDGES,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_REQUEST_AREA_PRESET,
    SERVICE_REQUEST_CHANNEL_LEVEL,
)
from .convert_config import convert_config
from .panel import async_register_dynalite_frontend
from .schema import BRIDGE_SCHEMA

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {vol.Optional(CONF_BRIDGES): vol.All(cv.ensure_list, [BRIDGE_SCHEMA])}
            ),
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dynalite platform."""
    conf = config.get(DOMAIN, {})
    LOGGER.debug("Setting up dynalite component config = %s", conf)
    hass.data[DOMAIN] = {}

    bridges = conf.get(CONF_BRIDGES, [])

    for bridge_conf in bridges:
        host = bridge_conf[CONF_HOST]
        LOGGER.debug("Starting config entry flow host=%s conf=%s", host, bridge_conf)

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=bridge_conf,
            )
        )

    async def dynalite_service(service_call: ServiceCall) -> None:
        data = service_call.data
        host = data.get(ATTR_HOST, "")
        bridges = [
            bridge
            for bridge in hass.data[DOMAIN].values()
            if not host or bridge.host == host
        ]
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

    await async_register_dynalite_frontend(hass)

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
    bridge = DynaliteBridge(hass, convert_config(entry.data))
    # need to do it before the listener
    hass.data[DOMAIN][entry.entry_id] = bridge
    entry.async_on_unload(entry.add_update_listener(async_entry_changed))

    if not await bridge.async_setup():
        LOGGER.error("Could not set up bridge for entry %s", entry.data)
        hass.data[DOMAIN][entry.entry_id] = None
        raise ConfigEntryNotReady

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.data)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
