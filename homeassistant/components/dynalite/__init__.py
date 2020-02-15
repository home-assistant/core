"""Support for the Dynalite networks."""
from dynalite_devices_lib import (
    CONF_ACTIVE,
    CONF_AREA,
    CONF_AUTODISCOVER,
    CONF_CHANNEL,
    CONF_DEFAULT,
    CONF_FADE,
    CONF_HIDDENENTITY,
    CONF_LOGLEVEL,
    CONF_NAME,
    CONF_POLLTIMER,
    CONF_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .const import CONF_BRIDGES, CONF_NOWAIT, DATA_CONFIGS, DOMAIN, LOGGER


def num_string(value):
    """Test if value is a string of digits, aka an integer."""
    new_value = str(value)
    if new_value.isdigit():
        return new_value
    raise vol.Invalid("Not a string with numbers")


CHANNEL_DATA_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(CONF_NAME): str,
            vol.Optional(CONF_FADE): vol.Coerce(float),
            vol.Optional(CONF_HIDDENENTITY, default=False): vol.Coerce(bool),
        }
    )
)

CHANNEL_SCHEMA = vol.Schema({num_string: vol.Any(CHANNEL_DATA_SCHEMA, None)})

AREA_DATA_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_NAME): str,
            vol.Optional(CONF_FADE): vol.Coerce(float),
            vol.Optional(CONF_CHANNEL): CHANNEL_SCHEMA,
        },
    )
)

AREA_SCHEMA = vol.Schema({num_string: vol.Any(AREA_DATA_SCHEMA, None)})

PLATFORM_DEFAULTS_SCHEMA = vol.Schema({vol.Optional(CONF_FADE): vol.Coerce(float)})


BRIDGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_LOGLEVEL): str,
        vol.Optional(CONF_AUTODISCOVER, default=False): vol.Coerce(bool),
        vol.Optional(CONF_POLLTIMER, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_AREA): AREA_SCHEMA,
        vol.Optional(CONF_DEFAULT): PLATFORM_DEFAULTS_SCHEMA,
        vol.Optional(CONF_ACTIVE, default=False): vol.Coerce(bool),
        vol.Optional(CONF_NOWAIT): vol.Coerce(bool),
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
    hass.data[DOMAIN][DATA_CONFIGS] = {}

    # User has configured bridges
    if CONF_BRIDGES not in conf:
        return True

    bridges = conf[CONF_BRIDGES]

    for bridge_conf in bridges:
        host = bridge_conf[CONF_HOST]
        LOGGER.debug("Starting config entry flow host=%s conf=%s", host, bridge_conf)

        # Store config in hass.data so the config entry can find it
        hass.data[DOMAIN][DATA_CONFIGS][host] = bridge_conf

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=bridge_conf,
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up a bridge from a config entry."""
    LOGGER.debug("Setting up entry %s", entry.data)

    bridge = DynaliteBridge(hass, entry.data)

    if not await bridge.async_setup():
        LOGGER.error("Could not set up bridge for entry %s", entry.data)
        return False
    hass.data[DOMAIN][entry.entry_id] = bridge

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.data)
    hass.data[DOMAIN].pop(entry.entry_id)
    result = await hass.config_entries.async_forward_entry_unload(entry, "light")
    return result
