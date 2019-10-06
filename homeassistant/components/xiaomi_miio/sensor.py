"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Sensor"
DATA_KEY = "sensor.xiaomi_miio"

MODEL_AIRQUALITYMONITOR_V1 = "zhimi.airmonitor.v1"
MODEL_AIRQUALITYMONITOR_S1 = "cgllc.airmonitor.s1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

ATTR_POWER = "power"
ATTR_CHARGING = "charging"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_DISPLAY_CLOCK = "display_clock"
ATTR_NIGHT_MODE = "night_mode"
ATTR_NIGHT_TIME_BEGIN = "night_time_begin"
ATTR_NIGHT_TIME_END = "night_time_end"
ATTR_SENSOR_STATE = "sensor_state"
ATTR_CO2 = "co2"
ATTR_HUMIDITY = "humidity"
ATTR_TEMPERATURE = "temperature"
ATTR_TVOC = "tvoc"
ATTR_MODEL = "model"

AVAILABLE_ATTRIBUTES_AIRQUALITYMONITOR_V1 = {
    ATTR_POWER: "power",
    ATTR_CHARGING: "usb_power",
    ATTR_BATTERY_LEVEL: "battery",
    ATTR_DISPLAY_CLOCK: "display_clock",
    ATTR_NIGHT_MODE: "night_mode",
    ATTR_NIGHT_TIME_BEGIN: "night_time_begin",
    ATTR_NIGHT_TIME_END: "night_time_end",
    ATTR_SENSOR_STATE: "sensor_state",
}

AVAILABLE_ATTRIBUTES_AIRQUALITYMONITOR_S1 = {
    ATTR_BATTERY_LEVEL: "battery",
    ATTR_CO2: "co2",
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
    ATTR_TVOC: "tvoc",
}


SUCCESS = ["ok"]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor from config."""
    from miio import AirQualityMonitor, DeviceException

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        air_quality_monitor = AirQualityMonitor(host, token)
        device_info = air_quality_monitor.info()
        model = device_info.model
        unique_id = f"{model}-{device_info.mac_address}"
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
        device = XiaomiAirQualityMonitor(name, air_quality_monitor, model, unique_id)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_entities([device], update_before_add=True)


class XiaomiAirQualityMonitor(Entity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id

        if self._model == MODEL_AIRQUALITYMONITOR_S1:
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRQUALITYMONITOR_S1
            self._unit_of_measurement = "µg/m3"
        else:
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRQUALITYMONITOR_V1
            self._unit_of_measurement = "AQI"

        self._state_attrs = {ATTR_MODEL: self._model}
        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

        self._icon = "mdi:cloud"
        self._available = None
        self._state = None

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_update(self):
        """Fetch state from the miio device."""
        from miio import DeviceException

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True

            if self._model == MODEL_AIRQUALITYMONITOR_S1:
                self._state = state.pm25
            else:
                self._state = state.aqi

            self._state_attrs.update(
                {
                    key: getattr(state, value)
                    for key, value in self._available_attributes.items()
                }
            )

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
