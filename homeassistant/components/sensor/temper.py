"""
Support for getting temperature from TEMPer devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.temper/
"""
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME, TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['temperusb==1.5.1']

CONF_SCALE = 'scale'
CONF_OFFSET = 'offset'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): vol.Coerce(str),
    vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
    vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float)
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Temper sensors."""
    from temperusb.temper import TemperHandler

    temp_unit = hass.config.units.temperature_unit
    name = config.get(CONF_NAME)
    scaling = {
        'scale': config.get(CONF_SCALE),
        'offset': config.get(CONF_OFFSET)
    }
    temper_devices = TemperHandler().get_devices()
    devices = []

    for idx, dev in enumerate(temper_devices):
        if idx != 0:
            name = name + '_' + str(idx)
        devices.append(TemperSensor(dev, temp_unit, name, scaling))

    add_devices(devices)


class TemperSensor(Entity):
    """Representation of a Temper temperature sensor."""

    def __init__(self, temper_device, temp_unit, name, scaling):
        """Initialize the sensor."""
        self.temper_device = temper_device
        self.temp_unit = temp_unit
        self.scale = scaling['scale']
        self.offset = scaling['offset']
        self.current_value = None
        self._name = name

        # set calibration data
        self.temper_device.set_calibration_data(
            scale=self.scale,
            offset=self.offset
        )

    @property
    def name(self):
        """Return the name of the temperature sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.temp_unit

    def update(self):
        """Retrieve latest state."""
        try:
            format_str = ('fahrenheit' if self.temp_unit == TEMP_FAHRENHEIT
                          else 'celsius')
            sensor_value = self.temper_device.get_temperature(format_str)
            self.current_value = round(sensor_value, 1)
        except IOError:
            _LOGGER.error('Failed to get temperature due to insufficient '
                          'permissions. Try running with "sudo"')
