"""Support for LaCrosse sensor components."""
from __future__ import annotations

from datetime import timedelta
import logging

import pylacrosse
from serial import SerialException
import voluptuous as vol

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_BAUD = "baud"
CONF_DATARATE = "datarate"
CONF_EXPIRE_AFTER = "expire_after"
CONF_FREQUENCY = "frequency"
CONF_JEELINK_LED = "led"
CONF_TOGGLE_INTERVAL = "toggle_interval"
CONF_TOGGLE_MASK = "toggle_mask"

DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD = "57600"
DEFAULT_EXPIRE_AFTER = 300

TYPES = ["battery", "humidity", "temperature"]

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_TYPE): vol.In(TYPES),
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
        vol.Optional(CONF_BAUD, default=DEFAULT_BAUD): cv.string,
        vol.Optional(CONF_DATARATE): cv.positive_int,
        vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        vol.Optional(CONF_FREQUENCY): cv.positive_int,
        vol.Optional(CONF_JEELINK_LED): cv.boolean,
        vol.Optional(CONF_TOGGLE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TOGGLE_MASK): cv.positive_int,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LaCrosse sensors."""
    usb_device = config[CONF_DEVICE]
    baud = int(config[CONF_BAUD])
    expire_after = config.get(CONF_EXPIRE_AFTER)

    _LOGGER.debug("%s %s", usb_device, baud)

    try:
        lacrosse = pylacrosse.LaCrosse(usb_device, baud)
        lacrosse.open()
    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: lacrosse.close())

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
            sensor_class(hass, lacrosse, device, name, expire_after, device_config)
        )

    add_entities(sensors)


class LaCrosseSensor(SensorEntity):
    """Implementation of a Lacrosse sensor."""

    _temperature = None
    _humidity = None
    _low_battery = None
    _new_battery = None

    def __init__(self, hass, lacrosse, device_id, name, expire_after, config):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._config = config
        self._value = None
        self._expire_after = expire_after
        self._expiration_trigger = None
        self._attr_name = name

        lacrosse.register_callback(
            int(self._config["id"]), self._callback_lacrosse, None
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "low_battery": self._low_battery,
            "new_battery": self._new_battery,
        }

    def _callback_lacrosse(self, lacrosse_sensor, user_data):
        """Handle a function that is called from pylacrosse with new values."""
        if self._expire_after is not None and self._expire_after > 0:
            # Reset old trigger
            if self._expiration_trigger:
                self._expiration_trigger()
                self._expiration_trigger = None

            # Set new trigger
            expiration_at = dt_util.utcnow() + timedelta(seconds=self._expire_after)

            self._expiration_trigger = async_track_point_in_utc_time(
                self.hass, self.value_is_expired, expiration_at
            )

        self._temperature = lacrosse_sensor.temperature
        self._humidity = lacrosse_sensor.humidity
        self._low_battery = lacrosse_sensor.low_battery
        self._new_battery = lacrosse_sensor.new_battery

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._value = None
        self.async_write_ha_state()


class LaCrosseTemperature(LaCrosseSensor):
    """Implementation of a Lacrosse temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._temperature


class LaCrosseHumidity(LaCrosseSensor):
    """Implementation of a Lacrosse humidity sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:water-percent"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._humidity


class LaCrosseBattery(LaCrosseSensor):
    """Implementation of a Lacrosse battery sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._low_battery is None:
            return None
        if self._low_battery is True:
            return "low"
        return "ok"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._low_battery is None:
            return "mdi:battery-unknown"
        if self._low_battery is True:
            return "mdi:battery-alert"
        return "mdi:battery"


TYPE_CLASSES = {
    "temperature": LaCrosseTemperature,
    "humidity": LaCrosseHumidity,
    "battery": LaCrosseBattery,
}
