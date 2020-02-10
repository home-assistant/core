"""Support for the Dynalite networks."""
from dynalite_devices_lib import BRIDGE_CONFIG_SCHEMA
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

# Loading the config flow file will register the flow
from .bridge import DynaliteBridge
from .config_flow import configured_hosts
from .const import CONF_BRIDGES, DATA_CONFIGS, DOMAIN, LOGGER

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_BRIDGES): vol.All(
                    cv.ensure_list, [BRIDGE_CONFIG_SCHEMA]
                )
            }
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

    configured = configured_hosts(hass)

    # User has configured bridges
    if CONF_BRIDGES not in conf:
        return True

    bridges = conf[CONF_BRIDGES]

    for bridge_conf in bridges:
        host = bridge_conf[CONF_HOST]
        LOGGER.debug("async_setup host=%s conf=%s", host, bridge_conf)

        # Store config in hass.data so the config entry can find it
        hass.data[DOMAIN][DATA_CONFIGS][host] = bridge_conf

        if host in configured:
            LOGGER.debug("async_setup host=%s already configured", host)
            continue

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
    host = entry.data[CONF_HOST]
    config = hass.data[DOMAIN][DATA_CONFIGS].get(host)

    if config is None:
        LOGGER.error("__init async_setup_entry empty config for host %s", host)
        return False

    bridge = DynaliteBridge(hass, entry)

    if not await bridge.async_setup():
        LOGGER.error("bridge.async_setup failed")
        return False
    hass.data[DOMAIN][entry.entry_id] = bridge
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    LOGGER.error("async_unload_entry %s", entry.data)
    bridge = hass.data[DOMAIN].pop(entry.entry_id)
    return await bridge.async_reset()
