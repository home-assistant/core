"""Support for Ambiclimate ac."""

import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY, DOMAIN, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_ON_OFF, STATE_HEAT)
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (ATTR_NAME, ATTR_TEMPERATURE,
                                 STATE_OFF, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['ambiclimate==0.1.1']

_LOGGER = logging.getLogger(__name__)

AMBICLIMATE_DATA = 'ambiclimate'
ATTR_VALUE = 'value'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONFIGURATOR_DESCRIPTION = 'To link your Ambiclimate account, ' \
                           'click the link, login, and authorize:'
CONFIGURATOR_LINK_NAME = 'Link Ambiclimate account'
CONFIGURATOR_SUBMIT_CAPTION = 'I authorized successfully'
DEFAULT_NAME = 'Ambiclimate'
SERVICE_COMFORT_FEEDBACK = 'send_comfort_feedback'
SERVICE_COMFORT_MODE = 'set_comfort_mode'
SERVICE_TEMPERATURE_MODE = 'set_temperature_mode'
STORAGE_KEY = 'ambiclimate_auth'
STORAGE_VERSION = 1

AUTH_CALLBACK_NAME = 'api:ambiclimate'
AUTH_CALLBACK_PATH = '/api/ambiclimate'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_ON_OFF)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
})

SEND_COMFORT_FEEDBACK_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_VALUE): cv.string,
})

SET_COMFORT_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
})

SET_TEMPERATURE_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_VALUE): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Ambiclimate heater."""
    import ambiclimate
    callback_url = '{}{}'.format(hass.config.api.base_url, AUTH_CALLBACK_PATH)
    oauth = ambiclimate.AmbiclimateOAuth(config.get(CONF_CLIENT_ID),
                                         config.get(CONF_CLIENT_SECRET),
                                         callback_url,
                                         async_get_clientsession(hass))

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    token_info = await store.async_load()

    if not token_info:
        _LOGGER.info("no token; requesting authorization")
        hass.http.register_view(AmbiclimateAuthCallbackView(config,
                                                            async_add_entities,
                                                            oauth,
                                                            store))

        def _call_request_config():
            configurator = hass.components.configurator
            req = configurator.request_config
            data = req(DEFAULT_NAME, lambda _: None,
                       link_name=CONFIGURATOR_LINK_NAME,
                       link_url=oauth.get_authorize_url(),
                       description=CONFIGURATOR_DESCRIPTION,
                       submit_caption=CONFIGURATOR_SUBMIT_CAPTION)
            hass.data[AMBICLIMATE_DATA] = data

        hass.async_add_job(_call_request_config)
        return

    if hass.data.get(AMBICLIMATE_DATA):
        def _call_request_config_done():
            configurator = hass.components.configurator
            configurator.request_done(hass.data.get(AMBICLIMATE_DATA))
            del hass.data[AMBICLIMATE_DATA]

        hass.async_add_job(_call_request_config_done)

    websession = async_get_clientsession(hass)
    data_connection = ambiclimate.AmbiclimateConnection(oauth,
                                                        token_info=token_info,
                                                        websession=websession)

    if await data_connection.refresh_access_token():
        await store.async_save(data_connection.token_info)

    if not await data_connection.find_devices():
        return

    devs = []
    for heater in data_connection.get_devices():
        await heater.update_device_info()
        devs.append(Ambiclimate(heater, store))

    async_add_entities(devs, True)

    async def send_comfort_feedback(service):
        """Send comfort feedback."""
        device_name = service.data.get(ATTR_NAME)
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_comfort_feedback(service.data.get(ATTR_VALUE))

    hass.services.async_register(DOMAIN,
                                 SERVICE_COMFORT_FEEDBACK,
                                 send_comfort_feedback,
                                 schema=SEND_COMFORT_FEEDBACK_SCHEMA)

    async def set_comfort_mode(service):
        """Set comfort mode."""
        device_name = service.data.get(ATTR_NAME)
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_comfort_mode()

    hass.services.async_register(DOMAIN,
                                 SERVICE_COMFORT_MODE,
                                 set_comfort_mode,
                                 schema=SET_COMFORT_MODE_SCHEMA)

    async def set_temperature_mode(service):
        """Set temperature mode."""
        device_name = service.data.get(ATTR_NAME)
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_temperature_mode(service.data.get(ATTR_VALUE))

    hass.services.async_register(DOMAIN,
                                 SERVICE_TEMPERATURE_MODE,
                                 set_temperature_mode,
                                 schema=SET_TEMPERATURE_MODE_SCHEMA)


class AmbiclimateAuthCallbackView(HomeAssistantView):
    """Ambiclimate Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    def __init__(self, config, async_add_entities, oauth, store):
        """Initialize."""
        self.config = config
        self.async_add_entities = async_add_entities
        self.oauth = oauth
        self.store = store

    async def get(self, request):
        """Receive authorization token."""
        hass = request.app['hass']

        token_info = await self.oauth.get_access_token(request.query['code'])
        await self.store.async_save(token_info)

        await async_setup_platform(hass, self.config, self.async_add_entities)


class Ambiclimate(ClimateDevice):
    """Representation of a Ambiclimate Thermostat device."""

    def __init__(self, heater, store):
        """Initialize the thermostat."""
        self._heater = heater
        self._data = dict()
        self._store = store

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.device_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._heater.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._data.get('target_temperature')

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._data.get('temperature')

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_CURRENT_HUMIDITY: self._data.get('humidity')}

    @property
    def is_on(self):
        """Return true if heater is on."""
        return self._data.get('power', '').lower() == 'on'

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._heater.get_min_temp()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._heater.get_max_temp()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def current_operation(self):
        """Return current operation."""
        return STATE_HEAT if self.is_on else STATE_OFF

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._heater.set_target_temperature(temperature)

    async def async_turn_on(self):
        """Turn device on."""
        await self._heater.turn_on()

    async def async_turn_off(self):
        """Turn device off."""
        await self._heater.turn_off()

    async def async_update(self):
        """Retrieve latest state."""
        token_info = await self._heater.control.refresh_access_token()
        if token_info:
            await self._store.async_save(token_info)
        self._data = await self._heater.update_device()
