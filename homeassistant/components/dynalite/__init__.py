"""Support for the Dynalite networks."""

import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .const import (
    CONF_ACTIVE,
    CONF_ACTIVE_INIT,
    CONF_ACTIVE_OFF,
    CONF_ACTIVE_ON,
    CONF_AREA,
    CONF_AUTO_DISCOVER,
    CONF_BRIDGES,
    CONF_CHANNEL,
    CONF_CHANNEL_TYPE,
    CONF_DEFAULT,
    CONF_FADE,
    CONF_NAME,
    CONF_NO_DEFAULT,
    CONF_POLLTIMER,
    CONF_PORT,
    CONF_PRESET,
    DEFAULT_CHANNEL_TYPE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ENTITY_PLATFORMS,
    LOGGER,
)


def num_string(value):
    """Test if value is a string of digits, aka an integer."""
    new_value = str(value)
    if new_value.isdigit():
        return new_value
    raise vol.Invalid("Not a string with numbers")


CHANNEL_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_CHANNEL_TYPE, default=DEFAULT_CHANNEL_TYPE): vol.Any(
            "light", "switch"
        ),
    }
)

CHANNEL_SCHEMA = vol.Schema({num_string: CHANNEL_DATA_SCHEMA})

PRESET_DATA_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Optional(CONF_FADE): vol.Coerce(float)}
)

PRESET_SCHEMA = vol.Schema({num_string: vol.Any(PRESET_DATA_SCHEMA, None)})


AREA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_NO_DEFAULT): vol.Coerce(bool),
        vol.Optional(CONF_CHANNEL): CHANNEL_SCHEMA,
        vol.Optional(CONF_PRESET): PRESET_SCHEMA,
    },
)

AREA_SCHEMA = vol.Schema({num_string: vol.Any(AREA_DATA_SCHEMA, None)})

PLATFORM_DEFAULTS_SCHEMA = vol.Schema({vol.Optional(CONF_FADE): vol.Coerce(float)})


BRIDGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_AUTO_DISCOVER, default=False): vol.Coerce(bool),
        vol.Optional(CONF_POLLTIMER, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_AREA): AREA_SCHEMA,
        vol.Optional(CONF_DEFAULT): PLATFORM_DEFAULTS_SCHEMA,
        vol.Optional(CONF_ACTIVE, default=False): vol.Any(
            CONF_ACTIVE_ON, CONF_ACTIVE_OFF, CONF_ACTIVE_INIT, cv.boolean
        ),
        vol.Optional(CONF_PRESET): PRESET_SCHEMA,
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


async def async_setup(hass, config):
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

    return True


async def async_entry_changed(hass, entry):
    """Reload entry since the data has changed."""
    LOGGER.debug("Reconfiguring entry %s", entry.data)
    bridge = hass.data[DOMAIN][entry.entry_id]
    bridge.reload_config(entry.data)
    LOGGER.debug("Reconfiguring entry finished %s", entry.data)


async def async_setup_entry(hass, entry):
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


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.data)
    hass.data[DOMAIN].pop(entry.entry_id)
    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in ENTITY_PLATFORMS
    ]
    results = await asyncio.gather(*tasks)
    return False not in results
