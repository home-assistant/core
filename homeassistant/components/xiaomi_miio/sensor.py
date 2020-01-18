"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
import logging

from miio import (
    AirQualityMonitor,
    DeviceException,
    Device,
)  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    ATTR_BATTERY_LEVEL,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Sensor"
DATA_KEY = "sensor.xiaomi_miio"

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
ATTR_MODEL = "model"
ATTR_TEMPERATURE = "temperature"
ATTR_HUMIDITY = "humidity"
ATTR_CO2 = "co2"
ATTR_PM2_5 = "pm25"
ATTR_TVOC = "tvoc"

DEVICE_CLASS_CO2 = "co2"
DEVICE_CLASS_PM2_5 = "pm25"
DEVICE_CLASS_TVOC = "tvoc"

MODEL_XIAOMI_AIRQUALITYMONITOR_S1 = "cgllc.airmonitor.s1"
MODEL_XIAOMI_AIRQUALITYMONITOR_B1 = "cgllc.airmonitor.b1"

SUCCESS = ["ok"]

SENSOR_TYPES = {
    "TEMPERATURE": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "unit_of_measurement": TEMP_CELSIUS,
        "icon": "mdi:thermometer",
        "state_attr": ATTR_TEMPERATURE,
    },
    "HUMIDITY": {
        "device_class": DEVICE_CLASS_HUMIDITY,
        "unit_of_measurement": "%",
        "icon": "mdi:water-percent",
        "state_attr": ATTR_HUMIDITY,
    },
    "CO2": {
        "device_class": DEVICE_CLASS_CO2,
        "unit_of_measurement": "ppm",
        "icon": "mdi:periodic-table-co2",
        "state_attr": ATTR_CO2,
    },
    "TVOC": {
        "device_class": DEVICE_CLASS_TVOC,
        "unit_of_measurement": "ppb",
        "icon": "mdi:cloud",
        "state_attr": ATTR_TVOC,
    },
    "PM25": {
        "device_class": DEVICE_CLASS_PM2_5,
        "unit_of_measurement": "µg/m3",
        "icon": "mdi:cloud",
        "state_attr": ATTR_PM2_5,
    },
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    all_devices = []
    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = await hass.async_add_executor_job(miio_device.info)
        model = device_info.model
        unique_id = f"{model}-{device_info.mac_address}"
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
        device = XiaomiAirQualityMonitor(
            name, AirQualityMonitor(host, token, model=model), model, unique_id
        )
        if (
            model == MODEL_XIAOMI_AIRQUALITYMONITOR_S1
            or model == MODEL_XIAOMI_AIRQUALITYMONITOR_B1
        ):
            for sensor in SENSOR_TYPES:
                cgllc_sensor = XiaomiCgllcSensor(
                    device, SENSOR_TYPES[sensor], unique_id
                )
                all_devices.append(cgllc_sensor)
        all_devices.append(device)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_entities(all_devices, update_before_add=True)


class XiaomiCgllcSensor(Entity):
    """Implementation of an XiaomiCgllcSensor device."""

    def __init__(self, device, sensor_type, unique_id):
        """Initialize the sensor."""
        self._device = device
        self._type = sensor_type
        self._name = device.name + " " + sensor_type["device_class"]
        self._unique_id = unique_id + "_" + sensor_type["device_class"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._type["device_class"]

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._type["icon"]

    @property
    def state(self):
        """Return the state of the device."""
        return self._device.device_state_attributes[self._type["state_attr"]]

    @property
    def available(self):
        """Return available of this entity."""
        return self._device.available

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._type["unit_of_measurement"]


class XiaomiAirQualityMonitor(Entity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id

        self._icon = "mdi:cloud"
        self._unit_of_measurement = "AQI"
        self._available = None
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}

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
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True

            if self._model == MODEL_XIAOMI_AIRQUALITYMONITOR_S1:
                self._state = state.pm25
                self._state_attrs.update(
                    {
                        ATTR_BATTERY_LEVEL: state.battery,
                        ATTR_CO2: state.co2,
                        ATTR_HUMIDITY: state.humidity,
                        ATTR_PM2_5: state.pm25,
                        ATTR_TEMPERATURE: state.temperature,
                        ATTR_TVOC: state.tvoc,
                    }
                )
            elif self._model == MODEL_XIAOMI_AIRQUALITYMONITOR_B1:
                self._state = state.pm25
                self._state_attrs.update(
                    {
                        ATTR_CO2: state.co2e,
                        ATTR_HUMIDITY: state.humidity,
                        ATTR_PM2_5: state.pm25,
                        ATTR_TEMPERATURE: state.temperature,
                        ATTR_TVOC: state.tvoc,
                    }
                )
            else:
                self._state = state.aqi
                self._state_attrs.update(
                    {
                        ATTR_POWER: state.power,
                        ATTR_CHARGING: state.usb_power,
                        ATTR_BATTERY_LEVEL: state.battery,
                        ATTR_DISPLAY_CLOCK: state.display_clock,
                        ATTR_NIGHT_MODE: state.night_mode,
                        ATTR_NIGHT_TIME_BEGIN: state.night_time_begin,
                        ATTR_NIGHT_TIME_END: state.night_time_end,
                        ATTR_SENSOR_STATE: state.sensor_state,
                    }
                )

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
