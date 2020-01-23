"""Support for deCONZ devices."""
import voluptuous as vol

from homeassistant.config_entries import _UNDEF
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .config_flow import get_master_gateway
from .const import CONF_BRIDGE_ID, CONF_GROUP_ID_BASE, CONF_MASTER_GATEWAY, DOMAIN
from .gateway import DeconzGateway
from .services import async_setup_services, async_unload_services

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({}, extra=vol.ALLOW_EXTRA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Old way of setting up deCONZ integrations."""
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

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if config_entry.unique_id is None:

        new_data = _UNDEF
        if CONF_BRIDGE_ID in config_entry.data:
            new_data = dict(config_entry.data)
            new_data[CONF_GROUP_ID_BASE] = config_entry.data[CONF_BRIDGE_ID]

        hass.config_entries.async_update_entry(
            config_entry, unique_id=gateway.api.config.bridgeid, data=new_data
        )

    hass.data[DOMAIN][config_entry.unique_id] = gateway

    await gateway.async_update_device_registry()

    await async_setup_services(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gateway.shutdown)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload deCONZ config entry."""
    gateway = hass.data[DOMAIN].pop(config_entry.unique_id)

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
    options = {**config_entry.options, CONF_MASTER_GATEWAY: master}

    hass.config_entries.async_update_entry(config_entry, options=options)
