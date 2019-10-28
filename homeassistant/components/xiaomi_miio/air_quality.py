"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
from miio import AirQualityMonitor, DeviceException
import voluptuous as vol

from homeassistant.components.air_quality import (
    AirQualityEntity,
    PLATFORM_SCHEMA,
    _LOGGER,
    ATTR_PM_2_5,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN, ATTR_TEMPERATURE
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Xiaomi Miio Air Quality Monitor"
DATA_KEY = "air_quality.xiaomi_miio"

ATTR_CO2E = "carbon_dioxide_equivalent"
ATTR_HUMIDITY = "relative_humidity"
ATTR_TVOC = "total_volatile_organic_compounds"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_SW_VERSION = "sw_version"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

PROP_TO_ATTR = {
    "carbon_dioxide_equivalent": ATTR_CO2E,
    "relative_humidity": ATTR_HUMIDITY,
    "particulate_matter_2_5": ATTR_PM_2_5,
    "temperature": ATTR_TEMPERATURE,
    "total_volatile_organic_compounds": ATTR_TVOC,
    "manufacturer": ATTR_MANUFACTURER,
    "model": ATTR_MODEL,
    "sw_version": ATTR_SW_VERSION,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    name = config.get(CONF_NAME)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        device = AirMonitorB1(name, AirQualityMonitor(host, token, model=None))

    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_entities([device], update_before_add=True)


class AirMonitorB1(AirQualityEntity):
    """Air Quality class for Xiaomi cgllc.airmonitor.b1 device."""

    def __init__(self, name, device):
        """Initialize the entity."""
        self._name = name
        self._device = device
        self._icon = "mdi:cloud"
        self._manufacturer = "Xiaomi"
        self._unit_of_measurement = "μg/m3"
        self._model = None
        self._mac_address = None
        self._sw_version = None
        self._carbon_dioxide_equivalent = None
        self._relative_humidity = None
        self._particulate_matter_2_5 = None
        self._temperature = None
        self._total_volatile_organic_compounds = None

    async def async_update(self):
        """Fetch state from the miio device."""

        try:
            if self._model is None:
                info = await self.hass.async_add_executor_job(self._device.info)
                self._model = info.model
                self._mac_address = info.mac_address
                self._sw_version = info.firmware_version

            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._carbon_dioxide_equivalent = state.co2e
            self._relative_humidity = round(state.humidity, 1)
            self._particulate_matter_2_5 = round(state.pm25, 1)
            self._temperature = round(state.temperature, 1)
            self._total_volatile_organic_compounds = round(state.tvoc, 3)

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device(self):
        """Return the name of this entity, if any."""
        return self._device

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def manufacturer(self):
        """Return the manufacturer version."""
        return self._manufacturer

    @property
    def model(self):
        """Return the device model."""
        return self._model

    @property
    def sw_version(self):
        """Return the software version."""
        return self._sw_version

    @property
    def mac_address(self):
        """Return the mac address."""
        return self._mac_address

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"{self._model}-{self._mac_address}"

    @property
    def carbon_dioxide_equivalent(self):
        """Return the CO2e (carbon dioxide equivalent) level."""
        return self._carbon_dioxide_equivalent

    @property
    def relative_humidity(self):
        """Return the humidity percentage."""
        return self._relative_humidity

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._particulate_matter_2_5

    @property
    def temperature(self):
        """Return the temperature in °C."""
        return self._temperature

    @property
    def total_volatile_organic_compounds(self):
        """Return the total volatile organic compounds."""
        return self._total_volatile_organic_compounds

    @property
    def state_attributes(self):
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

    @property
    def state(self):
        """Return the current state."""
        return self._particulate_matter_2_5
