"""
Support for deCONZ devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""
import logging

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_DECONZ
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery, aiohttp_client
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pydeconz==32']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'deconz'
DATA_DECONZ_ID = 'deconz_entities'

CONFIG_FILE = 'deconz.conf'

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


CONFIG_INSTRUCTIONS = """
Unlock your deCONZ gateway to register with Home Assistant.

1. [Go to deCONZ system settings](http://{}:{}/edit_system.html)
2. Press "Unlock Gateway" button

[deCONZ platform documentation](https://home-assistant.io/components/deconz/)
"""


async def async_setup(hass, config):
    """Set up services and configuration for deCONZ component."""
    result = False
    config_file = await hass.async_add_job(
        load_json, hass.config.path(CONFIG_FILE))

    async def async_deconz_discovered(service, discovery_info):
        """Call when deCONZ gateway has been found."""
        deconz_config = {}
        deconz_config[CONF_HOST] = discovery_info.get(CONF_HOST)
        deconz_config[CONF_PORT] = discovery_info.get(CONF_PORT)
        await async_request_configuration(hass, config, deconz_config)

    if config_file:
        result = await async_setup_deconz(hass, config, config_file)

    if not result and DOMAIN in config and CONF_HOST in config[DOMAIN]:
        deconz_config = config[DOMAIN]
        if CONF_API_KEY in deconz_config:
            result = await async_setup_deconz(hass, config, deconz_config)
        else:
            await async_request_configuration(hass, config, deconz_config)
            return True

    if not result:
        discovery.async_listen(hass, SERVICE_DECONZ, async_deconz_discovered)

    return True


async def async_setup_deconz(hass, config, deconz_config):
    """Set up a deCONZ session.

    Load config, group, light and sensor data for server information.
    Start websocket for push notification of state changes from deCONZ.
    """
    _LOGGER.debug("deCONZ config %s", deconz_config)
    from pydeconz import DeconzSession
    websession = async_get_clientsession(hass)
    deconz = DeconzSession(hass.loop, websession, **deconz_config)
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


async def async_request_configuration(hass, config, deconz_config):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    async def async_configuration_callback(data):
        """Set up actions to do when our configuration callback is called."""
        from pydeconz.utils import async_get_api_key
        api_key = await async_get_api_key(hass.loop, **deconz_config)
        if api_key:
            deconz_config[CONF_API_KEY] = api_key
            result = await async_setup_deconz(hass, config, deconz_config)
            if result:
                await hass.async_add_job(
                    save_json, hass.config.path(CONFIG_FILE), deconz_config)
                configurator.async_request_done(request_id)
                return
            else:
                configurator.async_notify_errors(
                    request_id, "Couldn't load configuration.")
        else:
            configurator.async_notify_errors(
                request_id, "Couldn't get an API key.")
        return

    instructions = CONFIG_INSTRUCTIONS.format(
        deconz_config[CONF_HOST], deconz_config[CONF_PORT])

    request_id = configurator.async_request_config(
        "deCONZ", async_configuration_callback,
        description=instructions,
        entity_picture="/static/images/logo_deconz.jpeg",
        submit_caption="I have unlocked the gateway",
    )


from homeassistant import config_entries


@config_entries.HANDLERS.register(DOMAIN)
class DeconzFlowHandler(config_entries.ConfigFlowHandler):
    """Handle a Deconz config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Deconz flow."""
        self.host = None
        self.port = None

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        # from aiohue.discovery import discover_nupnp

        print('step init - user input', user_input)

        if user_input is not None:
            self.host = user_input['host']
            self.port = user_input['port']
            return await self.async_step_link()
        URL_DISCOVER = 'https://dresden-light.appspot.com/discover'
        session = aiohttp_client.async_get_clientsession(self.hass)
        discovered = await session.get(URL_DISCOVER)
        json_dict = await discovered.json()
        print(json_dict)
        # try:
        #     with async_timeout.timeout(5):
        #         bridges = await discover_nupnp(websession=self._websession)
        # except asyncio.TimeoutError:
        #     return self.async_abort(
        #         reason='Unable to discover Hue bridges.'
        #     )

        # if not bridges:
        #     return self.async_abort(
        #         reason='No Philips Hue bridges discovered.'
        #     )

        # # Find already configured hosts
        # configured_hosts = set(
        #     entry.data['host'] for entry
        #     in self.hass.config_entries.async_entries(DOMAIN))

        # hosts = [bridge.host for bridge in bridges
        #          if bridge.host not in configured_hosts]

        # if not hosts:
        #     return self.async_abort(
        #         reason='All Philips Hue bridges are already configured.'
        #     )

        # elif len(hosts) == 1:
        #     self.host = hosts[0]
        #     return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            title='Identify deCONZ gateway',
            data_schema=vol.Schema({
                'host': str,
                'port': int,
            }),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Deconz bridge."""
        # import aiohue
        errors = {}

        print('step link - user input', user_input)

        if user_input is not None:
            # bridge = aiohue.Bridge(self.host, websession=self._websession)
            # try:
            #     with async_timeout.timeout(5):
            #         # Create auth token
            #         await bridge.create_user('home-assistant')
            #         # Fetches name and id
            #         await bridge.initialize()
            # except (asyncio.TimeoutError, aiohue.RequestError,
            #         aiohue.LinkButtonNotPressed):
            #     errors['base'] = 'Failed to register, please try again.'
            # except aiohue.AiohueException:
            #     errors['base'] = 'Unknown linking error occurred.'
            #     _LOGGER.exception('Uknown Hue linking error occurred')
            # else:
            #     return self.async_create_entry(
            #         title=bridge.config.name,
            #         data={
            #             'host': bridge.host,
            #             'bridge_id': bridge.config.bridgeid,
            #             'username': bridge.username,
            #         }
            #     )
            print('step link - user input', user_input)

        return self.async_show_form(
            step_id='link',
            title='Link deCONZ',
            description=instructions,
            errors=errors,
        )


async def async_setup_entry(hass, entry):
    """Set up a bridge for a config entry."""
    await hass.async_add_job(partial(
        setup_bridge, entry.data['host'], hass,
        username=entry.data['username']))
    return True
