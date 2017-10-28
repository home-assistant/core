"""
Support for LaCrosse sensor components.
"""
import logging
import pylacrosse
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import (ENTITY_ID_FORMAT, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_DEVICE, CONF_FRIENDLY_NAME, CONF_ID,
    CONF_SENSORS, CONF_TYPE, STATE_UNKNOWN, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pylacrosse']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lacrosse'

CONF_BAUD = 'baud'
CONF_EXPIRE_AFTER = 'expire_after'

DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_BAUD = '57600'
DEFAULT_EXPIRE_AFTER = 300

TYPES = ['battery', 'humidity', 'temperature']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_BAUD, default=DEFAULT_BAUD): cv.string,
})

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): vol.In(TYPES),
    vol.Required(CONF_ID): cv.positive_int,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
})

lacrosse = None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the LaCrosse component."""

    from serial import SerialException

    usb_device = config.get(CONF_DEVICE, DEFAULT_DEVICE)
    baud = int(config.get(CONF_BAUD, DEFAULT_BAUD))
    expire_after = config.get(CONF_EXPIRE_AFTER, DEFAULT_EXPIRE_AFTER)

    _LOGGER.debug("%s %s" % (usb_device, baud))

    try:
        lacrosse = pylacrosse.LaCrosse(usb_device, baud)
        lacrosse.open()
    except SerialException as e:
        _LOGGER.exception("Unable to open serial port for LaCrosse: %s", e)
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_serial_port)

    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        _LOGGER.debug("%s %s" % (device, device_config))

        typ = device_config.get(CONF_TYPE)
        try:
            sensor_class = TYPE_CLASSES[typ]
        except KeyError:
            _LOGGER.exception("Unknown LaCrosse sensor type: %s", typ)

        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        sensors.append(
            sensor_class(
                hass,
                lacrosse,
                device,
                friendly_name,
                expire_after,
                device_config
            )
        )

    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    add_devices(sensors)


def close_serial_port(*args):
    """Close the serial port uesed for the lacrosse."""
    lacrosse.close()


class LaCrosseSensor(Entity):
    """Implementation of a Lacrosse sensor."""

    _temperature = None
    _humidity = None
    _low_battery = None
    _new_battery = None

    def __init__(self, hass, lacrosse, device_id, friendly_name,
                 expire_after, config):
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT,
                                                  device_id, hass=hass)
        self._config = config
        self._name = friendly_name
        self._value = STATE_UNKNOWN
        self._expire_after = expire_after
        self._expiration_trigger = None

        lacrosse.register_callback(int(self._config["id"]),
                                   self._callback_lacrosse, None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def update(self, *args):
        """Get the latest data."""
        pass

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        attributes['low_battery'] = self._low_battery
        attributes['new_battery'] = self._new_battery
        return attributes

    def _callback_lacrosse(self, lacrosse_sensor, user_data):
        """Callback function that is called from pylacrosse with new values."""
        # auto-expire enabled?

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

        self._temperature = round(lacrosse_sensor.temperature * 2) / 2
        self._humidity = lacrosse_sensor.humidity
        self._low_battery = lacrosse_sensor.low_battery
        self._new_battery = lacrosse_sensor.new_battery

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._value = STATE_UNKNOWN
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
            state = 'na/a'
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
    "temperature": LaCrosseTemperature,
    "humidity": LaCrosseHumidity,
    "battery": LaCrosseBattery
}
