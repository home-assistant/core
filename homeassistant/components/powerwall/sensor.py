"""Support for August sensors."""
import logging

from tesla_powerwall import MeterType

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER,
    PERCENTAGE,
    POWER_KILO_WATT,
)

from .const import (
    ATTR_ENERGY_EXPORTED,
    ATTR_ENERGY_IMPORTED,
    ATTR_FREQUENCY,
    ATTR_INSTANT_AVERAGE_VOLTAGE,
    ATTR_INSTANT_TOTAL_CURRENT,
    ATTR_IS_ACTIVE,
    DOMAIN,
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


class PowerWallChargeSensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall charge sensor."""

    _attr_name = "Powerwall Charge"
    _attr_unit_of_measurement = PERCENTAGE
    _attr_device_class = DEVICE_CLASS_BATTERY

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_charge"

    @property
    def state(self):
        """Get the current value in percentage."""
        return round(self.coordinator.data[POWERWALL_API_CHARGE])


class PowerWallEnergySensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall Energy sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_unit_of_measurement = POWER_KILO_WATT
    _attr_device_class = DEVICE_CLASS_POWER

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
        self._attr_name = f"Powerwall {self._meter.value.title()} Now"
        self._attr_unique_id = (
            f"{self.base_unique_id}_{self._meter.value}_instant_power"
        )

    @property
    def state(self):
        """Get the current value in kW."""
        return (
            self.coordinator.data[POWERWALL_API_METERS]
            .get_meter(self._meter)
            .get_power(precision=3)
        )

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        meter = self.coordinator.data[POWERWALL_API_METERS].get_meter(self._meter)
        return {
            ATTR_FREQUENCY: round(meter.frequency, 1),
            ATTR_ENERGY_EXPORTED: meter.get_energy_exported(),
            ATTR_ENERGY_IMPORTED: meter.get_energy_imported(),
            ATTR_INSTANT_AVERAGE_VOLTAGE: round(meter.average_voltage, 1),
            ATTR_INSTANT_TOTAL_CURRENT: meter.get_instant_total_current(),
            ATTR_IS_ACTIVE: meter.is_active(),
        }
