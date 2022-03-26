"""Support for Somfy Thermostat Battery."""
from pymfy.api.devices.category import Category
from pymfy.api.devices.thermostat import Thermostat

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .entity import SomfyEntity

SUPPORTED_CATEGORIES = {Category.HVAC.value}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Somfy sensor platform."""
    domain_data = hass.data[DOMAIN]
    coordinator = domain_data[COORDINATOR]

    sensors = [
        SomfyThermostatBatterySensor(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if SUPPORTED_CATEGORIES & set(device.categories)
    ]

    async_add_entities(sensors)


class SomfyThermostatBatterySensor(SomfyEntity, SensorEntity):
    """Representation of a Somfy thermostat battery."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, device_id):
        """Initialize the Somfy device."""
        super().__init__(coordinator, device_id)
        self._climate = None
        self._create_device()

    def _create_device(self):
        """Update the device with the latest data."""
        self._climate = Thermostat(self.device, self.coordinator.client)

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._climate.get_battery()
