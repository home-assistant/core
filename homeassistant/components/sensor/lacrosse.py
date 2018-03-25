"""
Support for LaCrosse sensor components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.lacrosse/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_DEVICE, CONF_ID, CONF_NAME, CONF_SENSORS, CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP, TEMP_CELSIUS)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pylacrosse==0.3.1']

_LOGGER = logging.getLogger(__name__)

CONF_BAUD = 'baud'
CONF_DATARATE = 'datarate'
CONF_EXPIRE_AFTER = 'expire_after'
CONF_FREQUENCY = 'frequency'
CONF_JEELINK_LED = 'led'
CONF_TOGGLE_INTERVAL = 'toggle_interval'
CONF_TOGGLE_MASK = 'toggle_mask'

DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_BAUD = '57600'
DEFAULT_EXPIRE_AFTER = 300

TYPES = ['battery', 'humidity', 'temperature']

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
    vol.Required(CONF_TYPE): vol.In(TYPES),
    vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
    vol.Optional(CONF_BAUD, default=DEFAULT_BAUD): cv.string,
    vol.Optional(CONF_DATARATE): cv.positive_int,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_FREQUENCY): cv.positive_int,
    vol.Optional(CONF_JEELINK_LED): cv.boolean,
    vol.Optional(CONF_TOGGLE_INTERVAL): cv.positive_int,
    vol.Optional(CONF_TOGGLE_MASK): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the LaCrosse sensors."""
    import pylacrosse
    from serial import SerialException

    usb_device = config.get(CONF_DEVICE)
    baud = int(config.get(CONF_BAUD))
    expire_after = config.get(CONF_EXPIRE_AFTER)

    _LOGGER.debug("%s %s", usb_device, baud)

    try:
        lacrosse = pylacrosse.LaCrosse(usb_device, baud)
        lacrosse.open()
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lacrosse.close)

    if CONF_JEELINK_LED in config:
        lacrosse.led_mode_state(config.get(CONF_JEELINK_LED))
    if CONF_FREQUENCY in config:
        lacrosse.set_frequency(config.get(CONF_FREQUENCY))
    if CONF_DATARATE in config:
        lacrosse.set_datarate(config.get(CONF_DATARATE))
    if CONF_TOGGLE_INTERVAL in config:
        lacrosse.set_toggle_interval(config.get(CONF_TOGGLE_INTERVAL))
    if CONF_TOGGLE_MASK in config:
        lacrosse.set_toggle_mask(config.get(CONF_TOGGLE_MASK))

    lacrosse.start_scan()

    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        _LOGGER.debug("%s %s", device, device_config)

        typ = device_config.get(CONF_TYPE)
        sensor_class = TYPE_CLASSES[typ]
        name = device_config.get(CONF_NAME, device)

        sensors.append(
            sensor_class(
                hass, lacrosse, device, name, expire_after, device_config
            )
        )

    add_devices(sensors)


class LaCrosseSensor(Entity):
    """Implementation of a Lacrosse sensor."""

    _temperature = None
    _humidity = None
    _low_battery = None
    _new_battery = None

    def __init__(self, hass, lacrosse, device_id, name, expire_after, config):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._config = config
        self._name = name
        self._value = None
        self._expire_after = expire_after
        self._expiration_trigger = None

        lacrosse.register_callback(
            int(self._config['id']), self._callback_lacrosse, None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            'low_battery': self._low_battery,
            'new_battery': self._new_battery,
        }
        return attributes

    def _callback_lacrosse(self, lacrosse_sensor, user_data):
        """Handle a function that is called from pylacrosse with new values."""
        if self._expire_after is not None and self._expire_after > 0:
            # Reset old trigger
            if self._expiration_trigger:
                self._expiration_trigger()
                self._expiration_trigger = None

            # Set new trigger
            expiration_at = (
                dt_util.utcnow() + timedelta(seconds=self._expire_after))

            self._expiration_trigger = async_track_point_in_utc_time(
                self.hass, self.value_is_expired, expiration_at)

        self._temperature = lacrosse_sensor.temperature
        self._humidity = lacrosse_sensor.humidity
        self._low_battery = lacrosse_sensor.low_battery
        self._new_battery = lacrosse_sensor.new_battery

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._value = None
        self.async_schedule_update_ha_state()


class LaCrosseTemperature(LaCrosseSensor):
    """Implementation of a Lacrosse temperature sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._temperature


class LaCrosseHumidity(LaCrosseSensor):
    """Implementation of a Lacrosse humidity sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return '%'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._humidity

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:water-percent'


class LaCrosseBattery(LaCrosseSensor):
    """Implementation of a Lacrosse battery sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._low_battery is None:
            state = None
        elif self._low_battery is True:
            state = 'low'
        else:
            state = 'ok'
        return state

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._low_battery is None:
            icon = 'mdi:battery-unknown'
        elif self._low_battery is True:
            icon = 'mdi:battery-alert'
        else:
            icon = 'mdi:battery'
        return icon


TYPE_CLASSES = {
    'temperature': LaCrosseTemperature,
    'humidity': LaCrosseHumidity,
    'battery': LaCrosseBattery
}
