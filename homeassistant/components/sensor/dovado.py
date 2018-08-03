"""
Support for Dovado router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dovado/
"""
import logging
import re
from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util import slugify
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT, CONF_SENSORS,
    DEVICE_DEFAULT_NAME)
from homeassistant.components.sensor import (DOMAIN, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dovado==0.4.1']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SENSOR_UPLOAD = 'upload'
SENSOR_DOWNLOAD = 'download'
SENSOR_SIGNAL = 'signal'
SENSOR_NETWORK = 'network'
SENSOR_SMS_UNREAD = 'sms'

SENSORS = {
    SENSOR_NETWORK: ('signal strength', 'Network', None,
                     'mdi:access-point-network'),
    SENSOR_SIGNAL: ('signal strength', 'Signal Strength', '%',
                    'mdi:signal'),
    SENSOR_SMS_UNREAD: ('sms unread', 'SMS unread', '',
                        'mdi:message-text-outline'),
    SENSOR_UPLOAD: ('traffic modem tx', 'Sent', 'GB',
                    'mdi:cloud-upload'),
    SENSOR_DOWNLOAD: ('traffic modem rx', 'Received', 'GB',
                      'mdi:cloud-download'),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_SENSORS):
    vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Dovado platform for sensors."""
    return Dovado().setup(hass, config, add_devices)


class Dovado:
    """A connection to the router."""

    def __init__(self):
        """Initialize."""
        self.state = {}
        self._dovado = None

    def setup(self, hass, config, add_devices):
        """Set up the connection."""
        import dovado
        self._dovado = dovado.Dovado(
            config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
            config.get(CONF_HOST), config.get(CONF_PORT))

        if not self.update():
            return False

        def send_sms(service):
            """Send SMS through the router."""
            number = service.data.get('number')
            message = service.data.get('message')
            _LOGGER.debug("message for %s: %s", number, message)
            self._dovado.send_sms(number, message)

        if self.state.get('sms') == 'enabled':
            service_name = slugify("{} {}".format(self.name, 'send_sms'))
            hass.services.register(DOMAIN, service_name, send_sms)

        for sensor in SENSORS:
            if sensor in config.get(CONF_SENSORS, [sensor]):
                add_devices([DovadoSensor(self, sensor)])

        return True

    @property
    def name(self):
        """Name of the router."""
        return self.state.get("product name", DEVICE_DEFAULT_NAME)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        _LOGGER.info("Updating")
        try:
            self.state = self._dovado.state or {}
            if not self.state:
                return False
            self.state.update(
                connected=self.state.get("modem status") == "CONNECTED")
            _LOGGER.debug("Received: %s", self.state)
            return True
        except OSError as error:
            _LOGGER.warning("Could not contact the router: %s", error)


class DovadoSensor(Entity):
    """Representation of a Dovado sensor."""

    def __init__(self, dovado, sensor):
        """Initialize the sensor."""
        self._dovado = dovado
        self._sensor = sensor
        self._state = self._compute_state()

    def _compute_state(self):
        state = self._dovado.state.get(SENSORS[self._sensor][0])
        if self._sensor == SENSOR_NETWORK:
            match = re.search(r"\((.+)\)", state)
            return match.group(1) if match else None
        if self._sensor == SENSOR_SIGNAL:
            try:
                return int(state.split()[0])
            except ValueError:
                return 0
        if self._sensor == SENSOR_SMS_UNREAD:
            return int(state)
        if self._sensor in [SENSOR_UPLOAD, SENSOR_DOWNLOAD]:
            return round(float(state) / 1e6, 1)
        return state

    def update(self):
        """Update sensor values."""
        self._dovado.update()
        self._state = self._compute_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._dovado.name, SENSORS[self._sensor][1])

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return SENSORS[self._sensor][3]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSORS[self._sensor][2]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {k: v for k, v in self._dovado.state.items()
                if k not in ['date', 'time']}
