"""Support for power & energy sensors for VeSync outlets."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncBaseEntity
from .const import DOMAIN, VS_DISCOVERY, VS_SENSORS
from .switch import DEV_TYPE_TO_HA

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SENSORS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_SENSORS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) != "outlet":
            # Not an outlet that supports energy/power, so do not create sensor entities
            continue
        entities.append(VeSyncPowerSensor(dev))
        entities.append(VeSyncEnergySensor(dev))

    async_add_entities(entities, update_before_add=True)


class VeSyncSensorEntity(VeSyncBaseEntity, SensorEntity):
    """Representation of a sensor describing diagnostics of a VeSync outlet."""

    def __init__(self, plug):
        """Initialize the VeSync outlet device."""
        super().__init__(plug)
        self.smartplug = plug

    @property
    def entity_category(self):
        """Return the diagnostic entity category."""
        return EntityCategory.DIAGNOSTIC


class VeSyncPowerSensor(VeSyncSensorEntity):
    """Representation of current power use for a VeSync outlet."""

    @property
    def unique_id(self):
        """Return unique ID for power sensor on device."""
        return f"{super().unique_id}-power"

    @property
    def name(self):
        """Return sensor name."""
        return f"{super().name} current power"

    @property
    def device_class(self):
        """Return the power device class."""
        return SensorDeviceClass.POWER

    @property
    def native_value(self):
        """Return the current power usage in W."""
        return self.smartplug.power

    @property
    def native_unit_of_measurement(self):
        """Return the Watt unit of measurement."""
        return POWER_WATT

    @property
    def state_class(self):
        """Return the measurement state class."""
        return SensorStateClass.MEASUREMENT

    def update(self):
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncEnergySensor(VeSyncSensorEntity):
    """Representation of current day's energy use for a VeSync outlet."""

    def __init__(self, plug):
        """Initialize the VeSync outlet device."""
        super().__init__(plug)
        self.smartplug = plug

    @property
    def unique_id(self):
        """Return unique ID for power sensor on device."""
        return f"{super().unique_id}-energy"

    @property
    def name(self):
        """Return sensor name."""
        return f"{super().name} energy use today"

    @property
    def device_class(self):
        """Return the energy device class."""
        return SensorDeviceClass.ENERGY

    @property
    def native_value(self):
        """Return the today total energy usage in kWh."""
        return self.smartplug.energy_today

    @property
    def native_unit_of_measurement(self):
        """Return the kWh unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def state_class(self):
        """Return the total_increasing state class."""
        return SensorStateClass.TOTAL_INCREASING

    def update(self):
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncPm25Sensor(VeSyncSensorEntity):
    """Sensor for concentration of particulate matter less than 2.5 micrometers."""

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return an integer representing the concentration of particulate matter less than 2.5 micrometers."""

        return self.smartfan.details["air_quality_value"]

    @property
    def name(self):
        """Return sensor name."""
        return f"{super().name} PM2.5"

    @property
    def unique_id(self):
        """Return unique ID for power sensor on device."""
        return f"{super().unique_id}-pm25"


class VeSyncAirQualitySensor(VeSyncSensorEntity):
    """Sensor for air quality levels.

    Note: On the LV-PUR131S and derivatives this will be a text string.
    """

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the air quality level.

        Note: On the LV-PUR131S and derivatives this will be a text string.
        """
        return self.smartfan.details["air_quality"]

    @property
    def name(self):
        """Return sensor name."""
        return f"{super().name} Air Quality"

    @property
    def unique_id(self):
        """Return unique ID for power sensor on device."""
        return f"{super().unique_id}-air-quality"


class VeSyncFilterLifeSensor(VeSyncSensorEntity):
    """Sensor for remaining filter life as a percentage."""

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the remaining filter life as a percentage."""
        return self.smartfan.details["filter_life"]

    @property
    def name(self):
        """Return sensor name."""
        return f"{super().name} Filter Life"

    @property
    def unique_id(self):
        """Return unique ID for power sensor on device."""
        return f"{super().unique_id}-filter-life"
