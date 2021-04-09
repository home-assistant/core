"""Support for the Dynalite networks."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.cover import DEVICE_CLASSES_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEFAULT, CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .const import (
    ACTIVE_INIT,
    ACTIVE_OFF,
    ACTIVE_ON,
    ATTR_AREA,
    ATTR_CHANNEL,
    ATTR_HOST,
    CONF_ACTIVE,
    CONF_AREA,
    CONF_AUTO_DISCOVER,
    CONF_BRIDGES,
    CONF_CHANNEL,
    CONF_CHANNEL_COVER,
    CONF_CLOSE_PRESET,
    CONF_DEVICE_CLASS,
    CONF_DURATION,
    CONF_FADE,
    CONF_LEVEL,
    CONF_NO_DEFAULT,
    CONF_OPEN_PRESET,
    CONF_POLL_TIMER,
    CONF_PRESET,
    CONF_ROOM_OFF,
    CONF_ROOM_ON,
    CONF_STOP_PRESET,
    CONF_TEMPLATE,
    CONF_TILT_TIME,
    DEFAULT_CHANNEL_TYPE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TEMPLATES,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_REQUEST_AREA_PRESET,
    SERVICE_REQUEST_CHANNEL_LEVEL,
)


def num_string(value: int | str) -> str:
    """Test if value is a string of digits, aka an integer."""
    new_value = str(value)
    if new_value.isdigit():
        return new_value
    raise vol.Invalid("Not a string with numbers")


CHANNEL_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_TYPE, default=DEFAULT_CHANNEL_TYPE): vol.Any(
            "light", "switch"
        ),
    }
)

CHANNEL_SCHEMA = vol.Schema({num_string: CHANNEL_DATA_SCHEMA})

PRESET_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_LEVEL): vol.Coerce(float),
    }
)

PRESET_SCHEMA = vol.Schema({num_string: vol.Any(PRESET_DATA_SCHEMA, None)})

TEMPLATE_ROOM_SCHEMA = vol.Schema(
    {vol.Optional(CONF_ROOM_ON): num_string, vol.Optional(CONF_ROOM_OFF): num_string}
)

TEMPLATE_TIMECOVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CHANNEL_COVER): num_string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_OPEN_PRESET): num_string,
        vol.Optional(CONF_CLOSE_PRESET): num_string,
        vol.Optional(CONF_STOP_PRESET): num_string,
        vol.Optional(CONF_DURATION): vol.Coerce(float),
        vol.Optional(CONF_TILT_TIME): vol.Coerce(float),
    }
)

TEMPLATE_DATA_SCHEMA = vol.Any(TEMPLATE_ROOM_SCHEMA, TEMPLATE_TIMECOVER_SCHEMA)

TEMPLATE_SCHEMA = vol.Schema({str: TEMPLATE_DATA_SCHEMA})


def validate_area(config: dict[str, Any]) -> dict[str, Any]:
    """Validate that template parameters are only used if area is using the relevant template."""
    conf_set = set()
    for template in DEFAULT_TEMPLATES:
        for conf in DEFAULT_TEMPLATES[template]:
            conf_set.add(conf)
    if config.get(CONF_TEMPLATE):
        for conf in DEFAULT_TEMPLATES[config[CONF_TEMPLATE]]:
            conf_set.remove(conf)
    for conf in conf_set:
        if config.get(conf):
            raise vol.Invalid(
                f"{conf} should not be part of area {config[CONF_NAME]} config"
            )
    return config


AREA_DATA_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_TEMPLATE): vol.In(DEFAULT_TEMPLATES),
            vol.Optional(CONF_FADE): vol.Coerce(float),
            vol.Optional(CONF_NO_DEFAULT): cv.boolean,
            vol.Optional(CONF_CHANNEL): CHANNEL_SCHEMA,
            vol.Optional(CONF_PRESET): PRESET_SCHEMA,
            # the next ones can be part of the templates
            vol.Optional(CONF_ROOM_ON): num_string,
            vol.Optional(CONF_ROOM_OFF): num_string,
            vol.Optional(CONF_CHANNEL_COVER): num_string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_OPEN_PRESET): num_string,
            vol.Optional(CONF_CLOSE_PRESET): num_string,
            vol.Optional(CONF_STOP_PRESET): num_string,
            vol.Optional(CONF_DURATION): vol.Coerce(float),
            vol.Optional(CONF_TILT_TIME): vol.Coerce(float),
        },
        validate_area,
    )
)

AREA_SCHEMA = vol.Schema({num_string: vol.Any(AREA_DATA_SCHEMA, None)})

PLATFORM_DEFAULTS_SCHEMA = vol.Schema({vol.Optional(CONF_FADE): vol.Coerce(float)})


BRIDGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_AUTO_DISCOVER, default=False): vol.Coerce(bool),
        vol.Optional(CONF_POLL_TIMER, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_AREA): AREA_SCHEMA,
        vol.Optional(CONF_DEFAULT): PLATFORM_DEFAULTS_SCHEMA,
        vol.Optional(CONF_ACTIVE, default=False): vol.Any(
            ACTIVE_ON, ACTIVE_OFF, ACTIVE_INIT, cv.boolean
        ),
        vol.Optional(CONF_PRESET): PRESET_SCHEMA,
        vol.Optional(CONF_TEMPLATE): TEMPLATE_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_BRIDGES): vol.All(cv.ensure_list, [BRIDGE_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Dynalite platform."""
    conf = config.get(DOMAIN)
    LOGGER.debug("Setting up dynalite component config = %s", conf)

    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}

    # User has configured bridges
    if CONF_BRIDGES not in conf:
        return True

    bridges = conf[CONF_BRIDGES]

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

    for platform in PLATFORMS:
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
        for platform in PLATFORMS
    ]
    results = await asyncio.gather(*tasks)
    return False not in results
