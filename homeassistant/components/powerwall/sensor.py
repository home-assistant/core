"""Support for August sensors."""
import logging

from tesla_powerwall import MeterType

from homeassistant.const import DEVICE_CLASS_BATTERY, DEVICE_CLASS_POWER, PERCENTAGE

from .const import (
    ATTR_ENERGY_EXPORTED,
    ATTR_ENERGY_IMPORTED,
    ATTR_FREQUENCY,
    ATTR_INSTANT_AVERAGE_VOLTAGE,
    ATTR_IS_ACTIVE,
    DOMAIN,
    ENERGY_KILO_WATT,
    POWERWALL_API_CHARGE,
    POWERWALL_API_DEVICE_TYPE,
    POWERWALL_API_METERS,
    POWERWALL_API_SERIAL_NUMBERS,
    POWERWALL_API_SITE_INFO,
    POWERWALL_API_STATUS,
    POWERWALL_COORDINATOR,
)
from .entity import PowerWallEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    powerwall_data = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Powerwall_data: %s", powerwall_data)

    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    site_info = powerwall_data[POWERWALL_API_SITE_INFO]
    device_type = powerwall_data[POWERWALL_API_DEVICE_TYPE]
    status = powerwall_data[POWERWALL_API_STATUS]
    powerwalls_serial_numbers = powerwall_data[POWERWALL_API_SERIAL_NUMBERS]

    entities = []
    for meter in MeterType:
        entities.append(
            PowerWallEnergySensor(
                meter,
                coordinator,
                site_info,
                status,
                device_type,
                powerwalls_serial_numbers,
            )
        )

    entities.append(
        PowerWallChargeSensor(
            coordinator, site_info, status, device_type, powerwalls_serial_numbers
        )
    )

    async_add_entities(entities, True)


class PowerWallChargeSensor(PowerWallEntity):
    """Representation of an Powerwall charge sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def name(self):
        """Device Name."""
        return "Powerwall Charge"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_charge"

    @property
    def state(self):
        """Get the current value in percentage."""
        return round(self.coordinator.data[POWERWALL_API_CHARGE])


class PowerWallEnergySensor(PowerWallEntity):
    """Representation of an Powerwall Energy sensor."""

    def __init__(
        self,
        meter: MeterType,
        coordinator,
        site_info,
        status,
        device_type,
        powerwalls_serial_numbers,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator, site_info, status, device_type, powerwalls_serial_numbers
        )
        self._meter = meter

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT

    @property
    def name(self):
        """Device Name."""
        return f"Powerwall {self._meter.value.title()} Now"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_POWER

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self._meter.value}_instant_power"

    @property
    def state(self):
        """Get the current value in kW."""
        return (
            self.coordinator.data[POWERWALL_API_METERS]
            .get_meter(self._meter)
            .get_power(precision=3)
        )

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        meter = self.coordinator.data[POWERWALL_API_METERS].get_meter(self._meter)
        return {
            ATTR_FREQUENCY: round(meter.frequency, 1),
            ATTR_ENERGY_EXPORTED: meter.get_energy_exported(),
            ATTR_ENERGY_IMPORTED: meter.get_energy_imported(),
            ATTR_INSTANT_AVERAGE_VOLTAGE: round(meter.avarage_voltage, 1),
            ATTR_IS_ACTIVE: meter.is_active(),
        }
