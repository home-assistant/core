"""
Support for deCONZ devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import (
    aiohttp_client, discovery, config_validation as cv)
from homeassistant.util.json import load_json

# Loading the config flow file will register the flow
from .config_flow import configured_hosts
from .const import CONFIG_FILE, DATA_DECONZ_ID, DOMAIN, _LOGGER

REQUIREMENTS = ['pydeconz==36']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_FIELD = 'field'
SERVICE_ENTITY = 'entity'
SERVICE_DATA = 'data'

SERVICE_SCHEMA = vol.Schema({
    vol.Exclusive(SERVICE_FIELD, 'deconz_id'): cv.string,
    vol.Exclusive(SERVICE_ENTITY, 'deconz_id'): cv.entity_id,
    vol.Required(SERVICE_DATA): dict,
})


async def async_setup(hass, config):
    """Load configuration for deCONZ component.

    Discovery has loaded the component if DOMAIN is not present in config.
    """
    if DOMAIN in config:
        deconz_config = None
        config_file = await hass.async_add_job(
            load_json, hass.config.path(CONFIG_FILE))
        if config_file:
            deconz_config = config_file
        elif CONF_HOST in config[DOMAIN]:
            deconz_config = config[DOMAIN]
        if deconz_config and not configured_hosts(hass):
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN, source='import', data=deconz_config
            ))
    return True


async def async_setup_entry(hass, entry):
    """Set up a deCONZ bridge for a config entry."""
    if DOMAIN in hass.data:
        _LOGGER.error(
            "Config entry failed since one deCONZ instance already exists")
        return False
    result = await async_setup_deconz(hass, None, entry.data)
    if result:
        return True
    return False


async def async_setup_deconz(hass, config, deconz_config):
    """Set up a deCONZ session.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    _LOGGER.debug("deCONZ config %s", deconz_config)
    from pydeconz import DeconzSession
    session = aiohttp_client.async_get_clientsession(hass)
    deconz = DeconzSession(hass.loop, session, **deconz_config)
    result = await deconz.async_load_parameters()
    if result is False:
        _LOGGER.error("Failed to communicate with deCONZ")
        return False

    hass.data[DOMAIN] = deconz
    hass.data[DATA_DECONZ_ID] = {}

    for component in ['binary_sensor', 'light', 'scene', 'sensor']:
        hass.async_add_job(discovery.async_load_platform(
            hass, component, DOMAIN, {}, config))
    deconz.start()

    async def async_configure(call):
        """Set attribute of device in deCONZ.

        Field is a string representing a specific device in deCONZ
        e.g. field='/lights/1/state'.
        Entity_id can be used to retrieve the proper field.
        Data is a json object with what data you want to alter
        e.g. data={'on': true}.
        {
            "field": "/lights/1/state",
            "data": {"on": true}
        }
        See Dresden Elektroniks REST API documentation for details:
        http://dresden-elektronik.github.io/deconz-rest-doc/rest/
        """
        field = call.data.get(SERVICE_FIELD)
        entity_id = call.data.get(SERVICE_ENTITY)
        data = call.data.get(SERVICE_DATA)
        deconz = hass.data[DOMAIN]
        if entity_id:
            entities = hass.data.get(DATA_DECONZ_ID)
            if entities:
                field = entities.get(entity_id)
            if field is None:
                _LOGGER.error('Could not find the entity %s', entity_id)
                return
        await deconz.async_put_state(field, data)
    hass.services.async_register(
        DOMAIN, 'configure', async_configure, schema=SERVICE_SCHEMA)

    @callback
    def deconz_shutdown(event):
        """
        Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once - EventBus calls
        this method with the event as the first argument, which should not
        be passed on to deconz.close.
        """
        deconz.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, deconz_shutdown)
    return True
