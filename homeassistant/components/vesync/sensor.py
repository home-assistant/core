"""Support for power & energy sensors for VeSync outlets."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .common import VeSyncBaseEntity
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_SENSORS
from .switch import DEV_TYPE_TO_HA

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SENSORS), discover)
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

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
