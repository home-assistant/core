"""
Sensor for Mopar vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mopar/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_COMMAND, CONF_PASSWORD, CONF_PIN, CONF_USERNAME,
    LENGTH_KILOMETERS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['motorparts==1.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_VEHICLE_INDEX = 'vehicle_index'

COOKIE_FILE = 'mopar_cookies.pickle'

MIN_TIME_BETWEEN_UPDATES = timedelta(days=7)

SERVICE_REMOTE_COMMAND = 'mopar_remote_command'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_PIN): cv.positive_int,
})

REMOTE_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Required(ATTR_VEHICLE_INDEX): cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Mopar platform."""
    import motorparts
    cookie = hass.config.path(COOKIE_FILE)
    try:
        session = motorparts.get_session(
            config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
            config.get(CONF_PIN), cookie_path=cookie)
    except motorparts.MoparError:
        _LOGGER.error("Failed to login")
        return

    def _handle_service(service):
        """Handle service call."""
        index = service.data.get(ATTR_VEHICLE_INDEX)
        command = service.data.get(ATTR_COMMAND)
        try:
            motorparts.remote_command(session, command, index)
        except motorparts.MoparError as error:
            _LOGGER.error(str(error))

    hass.services.register(DOMAIN, SERVICE_REMOTE_COMMAND, _handle_service,
                           schema=REMOTE_COMMAND_SCHEMA)

    data = MoparData(session)
    add_devices([MoparSensor(data, index)
                 for index, _ in enumerate(data.vehicles)], True)


class MoparData:
    """Container for Mopar vehicle data.

    Prevents session expiry re-login race condition.
    """

    def __init__(self, session):
        """Initialize data."""
        self._session = session
        self.vehicles = []
        self.vhrs = {}
        self.tow_guides = {}
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Update data."""
        import motorparts
        _LOGGER.info("Updating vehicle data")
        try:
            self.vehicles = motorparts.get_summary(self._session)['vehicles']
        except motorparts.MoparError:
            _LOGGER.exception("Failed to get summary")
            return
        for index, _ in enumerate(self.vehicles):
            try:
                self.vhrs[index] = motorparts.get_report(self._session, index)
                self.tow_guides[index] = motorparts.get_tow_guide(
                    self._session, index)
            except motorparts.MoparError:
                _LOGGER.warning("Failed to update for vehicle index %s", index)


class MoparSensor(Entity):
    """Mopar vehicle sensor."""

    def __init__(self, data, index):
        """Initialize the sensor."""
        self._index = index
        self._vehicle = {}
        self._vhr = {}
        self._tow_guide = {}
        self._odometer = None
        self._data = data

    def update(self):
        """Update device state."""
        self._data.update()
        self._vehicle = self._data.vehicles[self._index]
        self._vhr = self._data.vhrs.get(self._index, {})
        self._tow_guide = self._data.tow_guides.get(self._index, {})
        if 'odometer' in self._vhr:
            odo = float(self._vhr['odometer'])
            self._odometer = int(self.hass.config.units.length(
                odo, LENGTH_KILOMETERS))

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {}'.format(
            self._vehicle['year'], self._vehicle['make'],
            self._vehicle['model'])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._odometer

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        import motorparts
        attributes = {
            ATTR_VEHICLE_INDEX: self._index,
            ATTR_ATTRIBUTION: motorparts.ATTRIBUTION
        }
        attributes.update(self._vehicle)
        attributes.update(self._vhr)
        attributes.update(self._tow_guide)
        return attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.hass.config.units.length_unit

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:car'
