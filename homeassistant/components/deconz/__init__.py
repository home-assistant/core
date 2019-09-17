"""Support for deCONZ devices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv

from .config_flow import get_master_gateway
from .const import CONF_BRIDGEID, CONF_MASTER_GATEWAY, DEFAULT_PORT, DOMAIN
from .gateway import DeconzGateway
from .services import async_setup_services, async_unload_services

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_API_KEY): cv.string,
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Load configuration for deCONZ component.

    Discovery has loaded the component if DOMAIN is not present in config.
    """
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        deconz_config = config[DOMAIN]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=deconz_config,
            )
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a deCONZ bridge for a config entry.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_update_master_gateway(hass, config_entry)

    gateway = DeconzGateway(hass, config_entry)

    if not await gateway.async_setup():
        return False

    hass.data[DOMAIN][gateway.bridgeid] = gateway

    await gateway.async_update_device_registry()

    await async_setup_services(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    gateway = hass.data[DOMAIN].pop(config_entry.data[CONF_BRIDGEID])

    if not hass.data[DOMAIN]:
        await async_unload_services(hass)

    elif gateway.master:
        await async_update_master_gateway(hass, config_entry)
        new_master_gateway = next(iter(hass.data[DOMAIN].values()))
        await async_update_master_gateway(hass, new_master_gateway.config_entry)

    return await gateway.async_reset()


async def async_update_master_gateway(hass, config_entry):
    """Update master gateway boolean.

    Called by setup_entry and unload_entry.
    Makes sure there is always one master available.
    """
    master = not get_master_gateway(hass)

    old_options = dict(config_entry.options)

    new_options = {CONF_MASTER_GATEWAY: master}

    options = {**old_options, **new_options}

    hass.config_entries.async_update_entry(config_entry, options=options)
