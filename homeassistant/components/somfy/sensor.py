"""Support for Somfy Thermostat Battery."""

from pymfy.api.devices.category import Category
from pymfy.api.devices.thermostat import Thermostat

from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE

from . import SomfyEntity
from .const import API, COORDINATOR, DOMAIN

SUPPORTED_CATEGORIES = {Category.HVAC.value}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy climate platform."""

    def get_thermostats():
        """Retrieve thermostats."""
        domain_data = hass.data[DOMAIN]
        coordinator = domain_data[COORDINATOR]
        api = domain_data[API]

        return [
            SomfyThermostatBatterySensor(coordinator, device_id, api)
            for device_id, device in coordinator.data.items()
            if SUPPORTED_CATEGORIES & set(device.categories)
        ]

    async_add_entities(await hass.async_add_executor_job(get_thermostats))


class SomfyThermostatBatterySensor(SomfyEntity):
    """Representation of a Somfy thermostat battery."""

    def __init__(self, coordinator, device_id, api):
        """Initialize the Somfy device."""
        super().__init__(coordinator, device_id, api)
        self._climate = None
        self._create_device()

    def _create_device(self):
        """Update the device with the latest data."""
        self._climate = Thermostat(self.device, self.api)

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._climate.get_battery()

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of the sensor."""
        return PERCENTAGE
