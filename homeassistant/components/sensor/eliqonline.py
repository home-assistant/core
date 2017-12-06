"""
Monitors home energy use for the ELIQ Online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eliqonline/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_ACCESS_TOKEN, CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['eliqonline==1.0.13']

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL_ID = 'channel_id'

DEFAULT_NAME = 'ELIQ Online'

ICON = 'mdi:gauge'

SCAN_INTERVAL = timedelta(seconds=60)

UNIT_OF_MEASUREMENT = 'W'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_CHANNEL_ID): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ELIQ Online sensor."""
    import eliqonline

    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    channel_id = config.get(CONF_CHANNEL_ID)

    api = eliqonline.API(access_token)

    try:
        _LOGGER.debug("Probing for access to ELIQ Online API")
        api.get_data_now(channelid=channel_id)
    except OSError as error:
        _LOGGER.error("Could not access the ELIQ Online API: %s", error)
        return False

    add_devices([EliqSensor(api, channel_id, name)], True)


class EliqSensor(Entity):
    """Implementation of an ELIQ Online sensor."""

    def __init__(self, api, channel_id, name):
        """Initialize the sensor."""
        self._name = name
        self._state = STATE_UNKNOWN
        self._api = api
        self._channel_id = channel_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UNIT_OF_MEASUREMENT

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data."""
        try:
            response = self._api.get_data_now(channelid=self._channel_id)
            self._state = int(response.power)
            _LOGGER.debug("Updated power from server %d W", self._state)
        except OSError as error:
            _LOGGER.warning("Could not connect to the ELIQ Online API: %s",
                            error)
