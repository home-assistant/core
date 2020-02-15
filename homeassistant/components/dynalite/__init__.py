"""Support for the Dynalite networks."""
from dynalite_devices_lib import BRIDGE_CONFIG_SCHEMA
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .const import CONF_BRIDGES, CONF_NOWAIT, DATA_CONFIGS, DOMAIN, LOGGER

EXT_BRIDGE_SCHEMA = BRIDGE_CONFIG_SCHEMA.extend(
    {vol.Optional(CONF_NOWAIT): vol.Coerce(bool)}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_BRIDGES): vol.All(cv.ensure_list, [EXT_BRIDGE_SCHEMA])}
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
        LOGGER.debug("async_setup host=%s conf=%s", host, bridge_conf)

        # Store config in hass.data so the config entry can find it
        hass.data[DOMAIN][DATA_CONFIGS][host] = bridge_conf

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={CONF_HOST: bridge_conf[CONF_HOST]},
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up a bridge from a config entry."""
    LOGGER.debug("__init async_setup_entry %s", entry.data)

    bridge = DynaliteBridge(hass, entry.data[CONF_HOST])

    if not await bridge.async_setup():
        LOGGER.error("bridge.async_setup failed")
        return False
    hass.data[DOMAIN][entry.entry_id] = bridge

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    LOGGER.debug("async_unload_entry %s", entry.data)
    hass.data[DOMAIN].pop(entry.entry_id)
    result = await hass.config_entries.async_forward_entry_unload(entry, "light")
    return result
