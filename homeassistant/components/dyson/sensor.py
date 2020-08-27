"""Support for Dyson Pure Cool Link Sensors."""
import logging

from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink

from homeassistant.const import STATE_OFF, TEMP_CELSIUS, TIME_HOURS, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity

from . import DYSON_DEVICES

SENSOR_UNITS = {
    "air_quality": None,
    "dust": None,
    "filter_life": TIME_HOURS,
    "humidity": UNIT_PERCENTAGE,
}

SENSOR_ICONS = {
    "air_quality": "mdi:fan",
    "dust": "mdi:cloud",
    "filter_life": "mdi:filter-outline",
    "humidity": "mdi:water-percent",
    "temperature": "mdi:thermometer",
}

DYSON_SENSOR_DEVICES = "dyson_sensor_devices"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dyson Sensors."""

    if discovery_info is None:
        return

    hass.data.setdefault(DYSON_SENSOR_DEVICES, [])
    unit = hass.config.units.temperature_unit
    devices = hass.data[DYSON_SENSOR_DEVICES]

    # Get Dyson Devices from parent component
    device_ids = [device.unique_id for device in hass.data[DYSON_SENSOR_DEVICES]]
    new_entities = []
    for device in hass.data[DYSON_DEVICES]:
        if isinstance(device, DysonPureCool):
            if f"{device.serial}-temperature" not in device_ids:
                new_entities.append(DysonTemperatureSensor(device, unit))
            if f"{device.serial}-humidity" not in device_ids:
                new_entities.append(DysonHumiditySensor(device))
        elif isinstance(device, DysonPureCoolLink):
            new_entities.append(DysonFilterLifeSensor(device))
            new_entities.append(DysonDustSensor(device))
            new_entities.append(DysonHumiditySensor(device))
            new_entities.append(DysonTemperatureSensor(device, unit))
            new_entities.append(DysonAirQualitySensor(device))

    if not new_entities:
        return

    devices.extend(new_entities)
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
        self.hass.async_add_executor_job(
            self._device.add_message_listener, self.on_message
        )

    def on_message(self, message):
        """Handle new messages which are received from the fan."""
        # Prevent refreshing if not needed
        if self._old_value is None or self._old_value != self.state:
            _LOGGER.debug("Message received for %s device: %s", self.name, message)
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

    @property
    def unique_id(self):
        """Return the sensor's unique id."""
        return f"{self._device.serial}-{self._sensor_type}"


class DysonFilterLifeSensor(DysonSensor):
    """Representation of Dyson Filter Life sensor (in hours)."""

    def __init__(self, device):
        """Create a new Dyson Filter Life sensor."""
        super().__init__(device, "filter_life")
        self._name = f"{self._device.name} Filter Life"

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
        super().__init__(device, "dust")
        self._name = f"{self._device.name} Dust"

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
        super().__init__(device, "humidity")
        self._name = f"{self._device.name} Humidity"

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
        super().__init__(device, "temperature")
        self._name = f"{self._device.name} Temperature"
        self._unit = unit

    @property
    def state(self):
        """Return Temperature value."""
        if self._device.environmental_state:
            temperature_kelvin = self._device.environmental_state.temperature
            if temperature_kelvin == 0:
                return STATE_OFF
            if self._unit == TEMP_CELSIUS:
                return float(f"{(temperature_kelvin - 273.15):.1f}")
            return float(f"{(temperature_kelvin * 9 / 5 - 459.67):.1f}")
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class DysonAirQualitySensor(DysonSensor):
    """Representation of Dyson Air Quality sensor (lower is better)."""

    def __init__(self, device):
        """Create a new Dyson Air Quality sensor."""
        super().__init__(device, "air_quality")
        self._name = f"{self._device.name} AQI"

    @property
    def state(self):
        """Return Air Quality value."""
        if self._device.environmental_state:
            return int(self._device.environmental_state.volatil_organic_compounds)
        return None
