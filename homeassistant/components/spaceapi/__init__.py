"""Support for the SpaceAPI."""
import logging

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ICON, ATTR_LATITUDE, ATTR_LOCATION, ATTR_LONGITUDE,
    ATTR_STATE, ATTR_UNIT_OF_MEASUREMENT, CONF_ADDRESS, CONF_EMAIL,
    CONF_ENTITY_ID, CONF_SENSORS, CONF_STATE, CONF_URL)
import homeassistant.core as ha
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = 'address'
ATTR_API = 'api'
ATTR_CLOSE = 'close'
ATTR_CONTACT = 'contact'
ATTR_ISSUE_REPORT_CHANNELS = 'issue_report_channels'
ATTR_LASTCHANGE = 'lastchange'
ATTR_LOGO = 'logo'
ATTR_NAME = 'name'
ATTR_OPEN = 'open'
ATTR_SENSORS = 'sensors'
ATTR_SPACE = 'space'
ATTR_UNIT = 'unit'
ATTR_URL = 'url'
ATTR_VALUE = 'value'

CONF_CONTACT = 'contact'
CONF_HUMIDITY = 'humidity'
CONF_ICON_CLOSED = 'icon_closed'
CONF_ICON_OPEN = 'icon_open'
CONF_ICONS = 'icons'
CONF_IRC = 'irc'
CONF_ISSUE_REPORT_CHANNELS = 'issue_report_channels'
CONF_LOCATION = 'location'
CONF_LOGO = 'logo'
CONF_MAILING_LIST = 'mailing_list'
CONF_PHONE = 'phone'
CONF_SPACE = 'space'
CONF_TEMPERATURE = 'temperature'
CONF_TWITTER = 'twitter'

DATA_SPACEAPI = 'data_spaceapi'
DOMAIN = 'spaceapi'

ISSUE_REPORT_CHANNELS = [CONF_EMAIL, CONF_IRC, CONF_MAILING_LIST, CONF_TWITTER]

SENSOR_TYPES = [CONF_HUMIDITY, CONF_TEMPERATURE]
SPACEAPI_VERSION = 0.13

URL_API_SPACEAPI = '/api/spaceapi'

LOCATION_SCHEMA = vol.Schema({
    vol.Optional(CONF_ADDRESS): cv.string,
}, required=True)

CONTACT_SCHEMA = vol.Schema({
    vol.Optional(CONF_EMAIL): cv.string,
    vol.Optional(CONF_IRC): cv.string,
    vol.Optional(CONF_MAILING_LIST): cv.string,
    vol.Optional(CONF_PHONE): cv.string,
    vol.Optional(CONF_TWITTER): cv.string,
}, required=False)

STATE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Inclusive(CONF_ICON_CLOSED, CONF_ICONS): cv.url,
    vol.Inclusive(CONF_ICON_OPEN, CONF_ICONS): cv.url,
}, required=False)

SENSOR_SCHEMA = vol.Schema(
    {vol.In(SENSOR_TYPES): [cv.entity_id]}
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CONTACT): CONTACT_SCHEMA,
        vol.Required(CONF_ISSUE_REPORT_CHANNELS):
            vol.All(cv.ensure_list, [vol.In(ISSUE_REPORT_CHANNELS)]),
        vol.Required(CONF_LOCATION): LOCATION_SCHEMA,
        vol.Required(CONF_LOGO): cv.url,
        vol.Required(CONF_SPACE): cv.string,
        vol.Required(CONF_STATE): STATE_SCHEMA,
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Register the SpaceAPI with the HTTP interface."""
    hass.data[DATA_SPACEAPI] = config[DOMAIN]
    hass.http.register_view(APISpaceApiView)

    return True


class APISpaceApiView(HomeAssistantView):
    """View to provide details according to the SpaceAPI."""

    url = URL_API_SPACEAPI
    name = 'api:spaceapi'

    @ha.callback
    def get(self, request):
        """Get SpaceAPI data."""
        hass = request.app['hass']
        spaceapi = dict(hass.data[DATA_SPACEAPI])
        is_sensors = spaceapi.get('sensors')

        location = {
            ATTR_ADDRESS: spaceapi[ATTR_LOCATION][CONF_ADDRESS],
            ATTR_LATITUDE: hass.config.latitude,
            ATTR_LONGITUDE: hass.config.longitude,
        }

        state_entity = spaceapi['state'][ATTR_ENTITY_ID]
        space_state = hass.states.get(state_entity)

        if space_state is not None:
            state = {
                ATTR_OPEN: space_state.state != 'off',
                ATTR_LASTCHANGE:
                    dt_util.as_timestamp(space_state.last_updated),
            }
        else:
            state = {ATTR_OPEN: 'null', ATTR_LASTCHANGE: 0}

        try:
            state[ATTR_ICON] = {
                ATTR_OPEN: spaceapi['state'][CONF_ICON_OPEN],
                ATTR_CLOSE: spaceapi['state'][CONF_ICON_CLOSED],
            }
        except KeyError:
            pass

        data = {
            ATTR_API: SPACEAPI_VERSION,
            ATTR_CONTACT: spaceapi[CONF_CONTACT],
            ATTR_ISSUE_REPORT_CHANNELS: spaceapi[CONF_ISSUE_REPORT_CHANNELS],
            ATTR_LOCATION: location,
            ATTR_LOGO: spaceapi[CONF_LOGO],
            ATTR_SPACE: spaceapi[CONF_SPACE],
            ATTR_STATE: state,
            ATTR_URL: spaceapi[CONF_URL],
        }

        if is_sensors is not None:
            sensors = {}
            for sensor_type in is_sensors:
                sensors[sensor_type] = []
                for sensor in spaceapi['sensors'][sensor_type]:
                    sensor_state = hass.states.get(sensor)
                    unit = sensor_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
                    value = sensor_state.state
                    sensor_data = {
                        ATTR_LOCATION: spaceapi[CONF_SPACE],
                        ATTR_NAME: sensor_state.name,
                        ATTR_UNIT: unit,
                        ATTR_VALUE: value,
                    }
                    sensors[sensor_type].append(sensor_data)
            data[ATTR_SENSORS] = sensors

        return self.json(data)
