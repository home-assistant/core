"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
from miio import AirQualityMonitor, Device, DeviceException
import voluptuous as vol
import logging

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady, NoEntitySpecifiedError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Air Quality Monitor"

MODEL_XIAOMI_AIRQUALITYMONITOR_S1 = "cgllc.airmonitor.s1"
MODEL_XIAOMI_AIRQUALITYMONITOR_B1 = "cgllc.airmonitor.b1"

ATTR_CO2E = "carbon_dioxide_equivalent"
ATTR_TVOC = "total_volatile_organic_compounds"
ATTR_TEMPERATURE = "temperature"
ATTR_HUMIDITY = "humidity"

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
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

PROP_TO_ATTR = {
    "carbon_dioxide_equivalent": ATTR_CO2E,
    "total_volatile_organic_compounds": ATTR_TVOC,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor from config."""

    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    miio_device = Device(host, token)

    try:
        device_info = await hass.async_add_executor_job(miio_device.info)
    except DeviceException:
        raise PlatformNotReady

    model = device_info.model
    unique_id = f"{model}-{device_info.mac_address}"
    _LOGGER.debug(
        "%s %s %s detected",
        model,
        device_info.firmware_version,
        device_info.hardware_version,
    )

    device = AirQualityMonitor(host, token, model=model)
    temperature_sensor = XiaomiCgllcSensor(name, SENSOR_TYPES["TEMPERATURE"], unique_id)
    humidity_sensor = XiaomiCgllcSensor(name, SENSOR_TYPES["HUMIDITY"], unique_id)
    if model == MODEL_XIAOMI_AIRQUALITYMONITOR_S1:
        entity = AirMonitorS1(
            name, device, unique_id, temperature_sensor, humidity_sensor
        )
    elif model == MODEL_XIAOMI_AIRQUALITYMONITOR_B1:
        entity = AirMonitorB1(
            name, device, unique_id, temperature_sensor, humidity_sensor
        )
    else:
        raise NoEntitySpecifiedError(f"Not support for entity {unique_id}")

    async_add_entities([entity, temperature_sensor, humidity_sensor], update_before_add=True)


class AirMonitorB1(AirQualityEntity):
    """Air Quality class for Xiaomi cgllc.airmonitor.b1 device."""

    def __init__(self, name, device, unique_id, temperature_sensor, humidity_sensor):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._unique_id = unique_id
        self._temperature_sensor = temperature_sensor
        self._humidity_sensor = humidity_sensor
        self._icon = "mdi:cloud"
        self._unit_of_measurement = "μg/m3"
        self._available = None
        self._carbon_dioxide = None
        self._carbon_dioxide_equivalent = None
        self._particulate_matter_2_5 = None
        self._total_volatile_organic_compounds = None

    async def async_update(self):
        """Fetch state from the miio device."""

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._carbon_dioxide_equivalent = state.co2e
            self._particulate_matter_2_5 = round(state.pm25, 1)
            self._total_volatile_organic_compounds = round(state.tvoc, 3)
            self._available = True
            self._temperature_sensor.set_state(state.temperature)
            self._humidity_sensor.set_state(state.humidity)
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return self._carbon_dioxide

    @property
    def carbon_dioxide_equivalent(self):
        """Return the CO2e (carbon dioxide equivalent) level."""
        return self._carbon_dioxide_equivalent

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._particulate_matter_2_5

    @property
    def total_volatile_organic_compounds(self):
        """Return the total volatile organic compounds."""
        return self._total_volatile_organic_compounds

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement


class AirMonitorS1(AirMonitorB1):
    """Air Quality class for Xiaomi cgllc.airmonitor.s1 device."""

    async def async_update(self):
        """Fetch state from the miio device."""

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)
            self._carbon_dioxide = state.co2
            self._particulate_matter_2_5 = state.pm25
            self._total_volatile_organic_compounds = state.tvoc
            self._available = True
            self._temperature_sensor.set_state(state.temperature)
            self._humidity_sensor.set_state(state.humidity)
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiCgllcSensor(Entity):
    """Implementation of an XiaomiCgllcSensor device."""

    def __init__(self, name, sensor_type, unique_id):
        """Initialize the sensor."""
        self._type = sensor_type
        self._unit_of_measurement = self._type["unit_of_measurement"]
        self._name = name + " " + sensor_type["device_class"]
        self._unique_id = unique_id + "_" + sensor_type["device_class"]
        self._state = None

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
        return self._state

    def set_state(self, state):
        """Update the sensor state."""
        self._state = state
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement
