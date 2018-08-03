"""
Support for USCIS Case Status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uscis/
"""

import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_FRIENDLY_NAME


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['uscisstatus==0.1.1']

DEFAULT_NAME = "USCIS"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required('case_id'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setting the platform in HASS and Case Information."""
    uscis = UscisSensor(config['case_id'], config[CONF_FRIENDLY_NAME])
    uscis.update()
    if uscis.valid_case_id:
        add_devices([uscis])
    else:
        _LOGGER.error("Setup USCIS Sensor Fail"
                      " check if your Case ID is Valid")


class UscisSensor(Entity):
    """USCIS Sensor will check case status on daily basis."""

    MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)

    CURRENT_STATUS = "current_status"
    LAST_CASE_UPDATE = "last_update_date"

    def __init__(self, case, name):
        """Initialize the sensor."""
        self._state = None
        self._case_id = case
        self._attributes = None
        self.valid_case_id = None
        self._name = name

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Using Request to access USCIS website and fetch data."""
        import uscisstatus
        try:
            status = uscisstatus.get_case_status(self._case_id)
            self._attributes = {
                self.CURRENT_STATUS: status['status']
            }
            self._state = status['date']
            self.valid_case_id = True

        except ValueError:
            _LOGGER("Please Check that you have valid USCIS case id")
            self.valid_case_id = False
