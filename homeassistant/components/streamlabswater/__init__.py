"""
Support for Streamlabs Water Monitor.

This component provides sensors that return the daily, monthly, and yearly
water usage as returned by the Streamlabs Water service. A binary sensor
is used to indicate whether the water monitor is in the home or away mode.

In addition to the sensors, a service is provided that can be used to set
the away mode of the water monitor.

The minimum configuration needed to get started is:

    streamlabswater:
      api_key: <your_api_key>

where the api_key is retrieved by following the instructions at:
https://developer.streamlabswater.com/docs/getting-started.html

By default the first location found will be used. You can specify a location:

    streamlabswater:
      api_key: <your_api_key>
      location_id: <your_location_id>

The away mode service is exposed at streamlabswater.set_away_mode where the
required parameter away_mode should be set to either home or away.
"""

import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['streamlabswater==1.0.1']

DOMAIN = 'streamlabswater'

_LOGGER = logging.getLogger(__name__)

ATTR_AWAY_MODE = 'away_mode'
SERVICE_SET_AWAY_MODE = 'set_away_mode'
AWAY_MODE_AWAY = 'away'
AWAY_MODE_HOME = 'home'

STREAMLABSWATER_COMPONENTS = [
    'sensor', 'binary_sensor'
]

CONF_LOCATION_ID = "location_id"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LOCATION_ID): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SET_AWAY_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_AWAY_MODE): vol.In([AWAY_MODE_AWAY, AWAY_MODE_HOME])
})


def setup(hass, config):
    """Set up the streamlabs water component."""
    from streamlabswater import streamlabswater

    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    location_id = conf.get(CONF_LOCATION_ID)

    client = streamlabswater.StreamlabsClient(api_key)
    locations = client.get_locations().get('locations')

    if locations is None:
        _LOGGER.error("Unable to retrieve locations. Verify API key.")
        return False

    if location_id is None:
        location = locations[0]
        location_id = location['locationId']
        _LOGGER.info("Streamlabs Water Monitor auto-detected location_id=%s",
                     location_id)
    else:
        location = next((
            l for l in locations if location_id == l['locationId']), None)
        if location is None:
            _LOGGER.error("Supplied location_id is invalid.")
            return False

    location_name = location['name']

    hass.data[DOMAIN] = {
        'client': client,
        'location_id': location_id,
        'location_name': location_name
    }

    for component in STREAMLABSWATER_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    def set_away_mode(service):
        away_mode = service.data.get(ATTR_AWAY_MODE)
        client.update_location(location_id, away_mode)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, set_away_mode,
        schema=SET_AWAY_MODE_SCHEMA)

    return True
