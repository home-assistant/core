"""
Sensor for Mopar vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mopar/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_PIN,
                                 ATTR_ATTRIBUTION, ATTR_COMMAND,
                                 LENGTH_KILOMETERS)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['motorparts==1.0.0']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(days=7)
DOMAIN = 'mopar'
DATA_MOPAR = DOMAIN
ATTR_VEHICLE_INDEX = 'vehicle_index'
SERVICE_REMOTE_COMMAND = 'remote_command'
COOKIE = 'mopar_cookies.pickle'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_PIN): cv.positive_int
})

REMOTE_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Required(ATTR_VEHICLE_INDEX): cv.positive_int
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Mopar platform."""
    import motorparts
    cookie = hass.config.path(COOKIE)
    try:
        session = motorparts.get_session(config.get(CONF_USERNAME),
                                         config.get(CONF_PASSWORD),
                                         config.get(CONF_PIN),
                                         cookie_path=cookie)
    except motorparts.MoparError:
        _LOGGER.error("failed to login")
        return False

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

    hass.data[DATA_MOPAR] = MoparData(session)
    add_devices([MoparSensor(hass, index)
                 for index, _ in enumerate(hass.data[DATA_MOPAR].vehicles)],
                True)
    return True


# pylint: disable=too-few-public-methods
class MoparData(object):
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
        _LOGGER.info("updating vehicle data")
        try:
            self.vehicles = motorparts.get_summary(self._session)['vehicles']
        except motorparts.MoparError:
            _LOGGER.exception("failed to get summary")
            return
        for index, _ in enumerate(self.vehicles):
            try:
                self.vhrs[index] = motorparts.get_report(self._session, index)
                self.tow_guides[index] = motorparts.get_tow_guide(
                    self._session, index)
            except motorparts.MoparError:
                _LOGGER.warning("failed to update for vehicle index %s", index)


class MoparSensor(Entity):
    """Mopar vehicle sensor."""

    def __init__(self, hass, index):
        """Initialize the sensor."""
        self._hass = hass
        self._index = index
        self._vehicle = {}
        self._vhr = {}
        self._tow_guide = {}

    def update(self):
        """Update device state."""
        data = self._hass.data[DATA_MOPAR]
        data.update()
        self._vehicle = data.vehicles[self._index]
        self._vhr = data.vhrs.get(self._index, {})
        self._tow_guide = data.tow_guides.get(self._index, {})

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {}'.format(self._vehicle['year'],
                                 self._vehicle['make'],
                                 self._vehicle['model'])

    @property
    def state(self):
        """Return the state of the sensor."""
        if 'odometer' not in self._vhr:
            return
        return int(self._hass.config.units.length(float(self._vhr['odometer']),
                                                  LENGTH_KILOMETERS))

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
        return self._hass.config.units.length_unit

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:car'
