"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
import logging

from miio import AirQualityMonitor, Device, DeviceException
import voluptuous as vol

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import NoEntitySpecifiedError, PlatformNotReady
import homeassistant.helpers.config_validation as cv

from .const import (
    MODEL_AIRQUALITYMONITOR_B1,
    MODEL_AIRQUALITYMONITOR_S1,
    MODEL_AIRQUALITYMONITOR_V1,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Air Quality Monitor"

ATTR_CO2E = "carbon_dioxide_equivalent"
ATTR_TVOC = "total_volatile_organic_compounds"
ATTR_TEMP = "temperature"
ATTR_HUM = "humidity"

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
    "temperature": ATTR_TEMP,
    "humidity": ATTR_HUM,
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

    if model == MODEL_AIRQUALITYMONITOR_S1:
        entity = AirMonitorS1(name, device, unique_id)
    elif model == MODEL_AIRQUALITYMONITOR_B1:
        entity = AirMonitorB1(name, device, unique_id)
    elif model == MODEL_AIRQUALITYMONITOR_V1:
        entity = AirMonitorV1(name, device, unique_id)
    else:
        raise NoEntitySpecifiedError(f"Not support for entity {unique_id}")

    async_add_entities([entity], update_before_add=True)


class AirMonitorB1(AirQualityEntity):
    """Air Quality class for Xiaomi cgllc.airmonitor.b1 device."""

    def __init__(self, name, device, unique_id):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._unique_id = unique_id
        self._icon = "mdi:cloud"
        self._unit_of_measurement = "μg/m3"
        self._available = None
        self._air_quality_index = None
        self._carbon_dioxide = None
        self._carbon_dioxide_equivalent = None
        self._particulate_matter_2_5 = None
        self._total_volatile_organic_compounds = None
        self._temperature = None
        self._humidity = None

    async def async_update(self):
        """Fetch state from the miio device."""
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)
            self._carbon_dioxide_equivalent = state.co2e
            self._particulate_matter_2_5 = round(state.pm25, 1)
            self._total_volatile_organic_compounds = round(state.tvoc, 3)
            self._temperature = round(state.temperature, 2)
            self._humidity = round(state.humidity, 2)
            self._available = True
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
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._air_quality_index

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
    def temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def humidity(self):
        """Return the current humidity."""
        return self._humidity

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
            self._temperature = state.temperature
            self._humidity = state.humidity
            self._available = True
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)


class AirMonitorV1(AirMonitorB1):
    """Air Quality class for Xiaomi cgllc.airmonitor.s1 device."""

    async def async_update(self):
        """Fetch state from the miio device."""
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)
            self._air_quality_index = state.aqi
            self._available = True
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return None
