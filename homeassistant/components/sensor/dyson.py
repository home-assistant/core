"""
Support for Dyson Pure Cool Link Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dyson/
"""
import logging

from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.const import STATE_OFF, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['dyson']

SENSOR_UNITS = {
    'air_quality': None,
    'dust': None,
    'filter_life': 'hours',
    'humidity': '%',
    'particulate_matter': 'μg/m3',
    'volatile_organic_compounds': None,
    'nitrogen_dioxide': None,
    'filter_state': '%'
}

SENSOR_ICONS = {
    'air_quality': 'mdi:fan',
    'dust': 'mdi:cloud',
    'filter_life': 'mdi:filter-outline',
    'humidity': 'mdi:water-percent',
    'temperature': 'mdi:thermometer',
    'particulate_matter': 'mdi:cloud',
    'volatile_organic_compounds': 'mdi:biohazard',
    'nitrogen_dioxide': 'mdi:cloud',
    'filter_state': 'mdi:filter-outline'
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson Sensors."""
    _LOGGER.debug("Creating new Dyson fans")
    devices = []
    unit = hass.config.units.temperature_unit
    # Get Dyson Devices from parent component
    from libpurecool.dyson_pure_cool_link import DysonPureCoolLink
    from libpurecool.dyson_pure_cool import DysonPureCool

    for device in hass.data[DYSON_DEVICES]:
        if isinstance(device, DysonPureCool):
            devices.append(DysonTemperatureSensor(device, unit))
            devices.append(DysonHumiditySensor(device))
            devices.append(DysonParticulateMatter25Sensor(device))
            devices.append(DysonParticulateMatter10Sensor(device))
            devices.append(DysonVolatileOrganicCompoundsSensor(device))
            devices.append(DysonNitrogenDioxideSensor(device))
            devices.append(DysonCarbonFilterStateSensor(device))
            devices.append(DysonHepaFilterStateSensor(device))
        elif isinstance(device, DysonPureCoolLink):
            devices.append(DysonFilterLifeSensor(device))
            devices.append(DysonDustSensor(device))
            devices.append(DysonHumiditySensor(device))
            devices.append(DysonTemperatureSensor(device, unit))
            devices.append(DysonAirQualitySensor(device))
    add_entities(devices)


class DysonSensor(Entity):
    """Representation of a generic Dyson sensor."""

    def __init__(self, device, sensor_type):
        """Create a new generic Dyson sensor."""
        self._device = device
        self._old_value = None
        self._name = None
        self._sensor_type = sensor_type

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(
            self._device.add_message_listener, self.on_message)

    def on_message(self, message):
        """Handle new messages which are received from the fan."""
        # Prevent refreshing if not needed
        if self._old_value is None or self._old_value != self.state:
            _LOGGER.debug("Message received for %s device: %s", self.name,
                          message)
            self._old_value = self.state
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the Dyson sensor name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS[self._sensor_type]

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return SENSOR_ICONS[self._sensor_type]


class DysonFilterLifeSensor(DysonSensor):
    """Representation of Dyson Filter Life sensor (in hours)."""

    def __init__(self, device):
        """Create a new Dyson Filter Life sensor."""
        super().__init__(device, 'filter_life')
        self._name = "{} Filter Life".format(self._device.name)

    @property
    def state(self):
        """Return filter life in hours."""
        if self._device.state:
            return int(self._device.state.filter_life)
        return None


class DysonDustSensor(DysonSensor):
    """Representation of Dyson Dust sensor (lower is better)."""

    def __init__(self, device):
        """Create a new Dyson Dust sensor."""
        super().__init__(device, 'dust')
        self._name = "{} Dust".format(self._device.name)

    @property
    def state(self):
        """Return Dust value."""
        if self._device.environmental_state:
            return self._device.environmental_state.dust
        return None


class DysonHumiditySensor(DysonSensor):
    """Representation of Dyson Humidity sensor."""

    def __init__(self, device):
        """Create a new Dyson Humidity sensor."""
        super().__init__(device, 'humidity')
        self._name = "{} Humidity".format(self._device.name)

    @property
    def state(self):
        """Return Humidity value."""
        if self._device.environmental_state:
            if self._device.environmental_state.humidity == 0:
                return STATE_OFF
            return self._device.environmental_state.humidity
        return None


class DysonTemperatureSensor(DysonSensor):
    """Representation of Dyson Temperature sensor."""

    def __init__(self, device, unit):
        """Create a new Dyson Temperature sensor."""
        super().__init__(device, 'temperature')
        self._name = "{} Temperature".format(self._device.name)
        self._unit = unit

    @property
    def state(self):
        """Return Temperature value."""
        if self._device.environmental_state:
            temperature_kelvin = self._device.environmental_state.temperature
            if temperature_kelvin == 0:
                return STATE_OFF
            if self._unit == TEMP_CELSIUS:
                return float("{0:.1f}".format(temperature_kelvin - 273.15))
            return float("{0:.1f}".format(temperature_kelvin * 9 / 5 - 459.67))
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class DysonAirQualitySensor(DysonSensor):
    """Representation of Dyson Air Quality sensor (lower is better)."""

    def __init__(self, device):
        """Create a new Dyson Air Quality sensor."""
        super().__init__(device, 'air_quality')
        self._name = "{} AQI".format(self._device.name)

    @property
    def state(self):
        """Return Air Quality value."""
        if self._device.environmental_state:
            return self._device.environmental_state.volatil_organic_compounds
        return None


class DysonParticulateMatter25Sensor(DysonSensor):
    """Representation of Dyson pm25 sensor."""

    def __init__(self, device):
        """Create a new Dyson pm25 sensor."""
        super().__init__(device, 'particulate_matter')
        self._name = "{} particulate matter 2.5 μg/m3"\
            .format(self._device.name)

    @property
    def state(self):
        """Return pm25 level."""
        if self._device.state:
            return int(self._device.environmental_state.particulate_matter_25)
        return None


class DysonParticulateMatter10Sensor(DysonSensor):
    """Representation of Dyson pm10 sensor."""

    def __init__(self, device):
        """Create a new Dyson pm10 sensor."""
        super().__init__(device, 'particulate_matter')
        self._name = "{} particulate matter 10 μg/m3".format(self._device.name)

    @property
    def state(self):
        """Return pm10 level."""
        if self._device.state:
            return int(self._device.environmental_state.particulate_matter_10)
        return None


class DysonNitrogenDioxideSensor(DysonSensor):
    """Representation of Dyson no2 sensor."""

    def __init__(self, device):
        """Create a new Dyson no2 sensor."""
        super().__init__(device, 'nitrogen_dioxide')
        self._name = "{} nitrogen dioxide".format(self._device.name)

    @property
    def state(self):
        """Return no2 level."""
        if self._device.state:
            return int(self._device.environmental_state.nitrogen_dioxide)
        return None


class DysonVolatileOrganicCompoundsSensor(DysonSensor):
    """Representation of Dyson VOC sensor."""

    def __init__(self, device):
        """Create a new Dyson voc sensor."""
        super().__init__(device, 'volatile_organic_compounds')
        self._name = "{} volatile organic compounds".format(self._device.name)

    @property
    def state(self):
        """Return voc level."""
        if self._device.state:
            return int(self._device.environmental_state.
                       volatile_organic_compounds)
        return None


class DysonCarbonFilterStateSensor(DysonSensor):
    """Representation of Dyson carbon filter state sensor (in %)."""

    def __init__(self, device):
        """Create a new Dyson carbon filter state sensor."""
        DysonSensor.__init__(self, device, 'filter_state')
        self._name = "{} carbon filter state".format(self._device.name)

    @property
    def state(self):
        """Return carbon filter state in %."""
        if self._device.state:
            return int(self._device.state.carbon_filter_state)
        return None


class DysonHepaFilterStateSensor(DysonSensor):
    """Representation of Dyson carbon filter state sensor (in %)."""

    def __init__(self, device):
        """Create a new Dyson carbon filter state sensor."""
        DysonSensor.__init__(self, device, 'filter_state')
        self._name = "{} hepa filter state".format(self._device.name)

    @property
    def state(self):
        """Return hepa filter state in %."""
        if self._device.state:
            return int(self._device.state.hepa_filter_state)
        return None
