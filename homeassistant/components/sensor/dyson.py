"""
Support for Dyson Pure Cool Link Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dyson/
"""
import asyncio
import logging

from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.const import STATE_OFF, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['dyson']

SENSOR_UNITS = {
    'air_quality': 'level',
    'dust': 'level',
    'filter_life': 'hours',
    'humidity': '%',
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson Sensors."""
    _LOGGER.debug("Creating new Dyson fans")
    devices = []
    unit = hass.config.units.temperature_unit
    # Get Dyson Devices from parent component
    from libpurecoollink.dyson_pure_cool_link import DysonPureCoolLink
    for device in [d for d in hass.data[DYSON_DEVICES] if
                   isinstance(d, DysonPureCoolLink)]:
        devices.append(DysonFilterLifeSensor(hass, device))
        devices.append(DysonDustSensor(hass, device))
        devices.append(DysonHumiditySensor(hass, device))
        devices.append(DysonTemperatureSensor(hass, device, unit))
        devices.append(DysonAirQualitySensor(hass, device))
    add_entities(devices)


class DysonSensor(Entity):
    """Representation of Dyson sensor."""

    def __init__(self, hass, device):
        """Create a new Dyson filter life sensor."""
        self.hass = hass
        self._device = device
        self._old_value = None
        self._name = None

    @asyncio.coroutine
    def async_added_to_hass(self):
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
        """Return the name of the dyson sensor name."""
        return self._name


class DysonFilterLifeSensor(DysonSensor):
    """Representation of Dyson filter life sensor (in hours)."""

    def __init__(self, hass, device):
        """Create a new Dyson filter life sensor."""
        DysonSensor.__init__(self, hass, device)
        self._name = "{} filter life".format(self._device.name)

    @property
    def state(self):
        """Return filter life in hours."""
        if self._device.state:
            return int(self._device.state.filter_life)
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS['filter_life']


class DysonDustSensor(DysonSensor):
    """Representation of Dyson Dust sensor (lower is better)."""

    def __init__(self, hass, device):
        """Create a new Dyson Dust sensor."""
        DysonSensor.__init__(self, hass, device)
        self._name = "{} dust".format(self._device.name)

    @property
    def state(self):
        """Return Dust value."""
        if self._device.environmental_state:
            return self._device.environmental_state.dust
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS['dust']


class DysonHumiditySensor(DysonSensor):
    """Representation of Dyson Humidity sensor."""

    def __init__(self, hass, device):
        """Create a new Dyson Humidity sensor."""
        DysonSensor.__init__(self, hass, device)
        self._name = "{} humidity".format(self._device.name)

    @property
    def state(self):
        """Return Dust value."""
        if self._device.environmental_state:
            if self._device.environmental_state.humidity == 0:
                return STATE_OFF
            return self._device.environmental_state.humidity
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS['humidity']


class DysonTemperatureSensor(DysonSensor):
    """Representation of Dyson Temperature sensor."""

    def __init__(self, hass, device, unit):
        """Create a new Dyson Temperature sensor."""
        DysonSensor.__init__(self, hass, device)
        self._name = "{} temperature".format(self._device.name)
        self._unit = unit

    @property
    def state(self):
        """Return Dust value."""
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

    def __init__(self, hass, device):
        """Create a new Dyson Air Quality sensor."""
        DysonSensor.__init__(self, hass, device)
        self._name = "{} air quality".format(self._device.name)

    @property
    def state(self):
        """Return Air Quality value."""
        if self._device.environmental_state:
            return self._device.environmental_state.volatil_organic_compounds
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS['air_quality']
