"""Support for powerwall sensors."""
from __future__ import annotations

from typing import Any

from tesla_powerwall import Meter, MeterType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, PERCENTAGE, POWER_KILO_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_FREQUENCY,
    ATTR_INSTANT_AVERAGE_VOLTAGE,
    ATTR_INSTANT_TOTAL_CURRENT,
    ATTR_IS_ACTIVE,
    DOMAIN,
    POWERWALL_COORDINATOR,
)
from .entity import PowerWallEntity
from .models import PowerwallData, PowerwallRuntimeData

_METER_DIRECTION_EXPORT = "export"
_METER_DIRECTION_IMPORT = "import"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the powerwall sensors."""
    powerwall_data: PowerwallRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    assert coordinator is not None
    data: PowerwallData = coordinator.data
    entities: list[
        PowerWallEnergySensor
        | PowerWallImportSensor
        | PowerWallExportSensor
        | PowerWallChargeSensor
        | PowerWallBackupReserveSensor
    ] = [
        PowerWallChargeSensor(powerwall_data),
        PowerWallBackupReserveSensor(powerwall_data),
    ]

    for meter in data.meters.meters:
        entities.extend(
            [
                PowerWallEnergySensor(powerwall_data, meter),
                PowerWallExportSensor(powerwall_data, meter),
                PowerWallImportSensor(powerwall_data, meter),
            ]
        )

    async_add_entities(entities)


class PowerWallChargeSensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall charge sensor."""

    _attr_name = "Powerwall Charge"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_charge"

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return round(self.data.charge)


class PowerWallEnergySensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall Energy sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self, powerwall_data: PowerwallRuntimeData, meter: MeterType) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._meter = meter
        self._attr_name = f"Powerwall {self._meter.value.title()} Now"
        self._attr_unique_id = (
            f"{self.base_unique_id}_{self._meter.value}_instant_power"
        )

    @property
    def native_value(self) -> float:
        """Get the current value in kW."""
        return self.data.meters.get_meter(self._meter).get_power(precision=3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        meter = self.data.meters.get_meter(self._meter)
        return {
            ATTR_FREQUENCY: round(meter.frequency, 1),
            ATTR_INSTANT_AVERAGE_VOLTAGE: round(meter.average_voltage, 1),
            ATTR_INSTANT_TOTAL_CURRENT: meter.get_instant_total_current(),
            ATTR_IS_ACTIVE: meter.is_active(),
        }


class PowerWallBackupReserveSensor(PowerWallEntity, SensorEntity):
    """Representation of the Powerwall backup reserve setting."""

    _attr_name = "Powerwall Backup Reserve"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_backup_reserve"

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return round(self.data.backup_reserve)


class PowerWallEnergyDirectionSensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall Direction Energy sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
        meter_direction: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._meter = meter
        self._attr_name = f"Powerwall {meter.value.title()} {meter_direction.title()}"
        self._attr_unique_id = f"{self.base_unique_id}_{meter.value}_{meter_direction}"

    @property
    def available(self) -> bool:
        """Check if the reading is actually available.

        The device reports 0 when something goes wrong which
        we do not want to include in statistics and its a
        transient data error.
        """
        return super().available and self.native_value != 0

    @property
    def meter(self) -> Meter:
        """Get the meter for the sensor."""
        return self.data.meters.get_meter(self._meter)


class PowerWallExportSensor(PowerWallEnergyDirectionSensor):
    """Representation of an Powerwall Export sensor."""

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data, meter, _METER_DIRECTION_EXPORT)

    @property
    def native_value(self) -> float:
        """Get the current value in kWh."""
        return self.meter.get_energy_exported()


class PowerWallImportSensor(PowerWallEnergyDirectionSensor):
    """Representation of an Powerwall Import sensor."""

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data, meter, _METER_DIRECTION_IMPORT)

    @property
    def native_value(self) -> float:
        """Get the current value in kWh."""
        return self.meter.get_energy_imported()
