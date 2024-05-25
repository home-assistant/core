"""Support for Solax inverter via local API."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from solax.inverter import InverterResponse
from solax.units import Units

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SolaxConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import Reset, SolaxDataUpdateCoordinator

DEFAULT_PORT = 80


SENSOR_DESCRIPTIONS: dict[tuple[Units, bool, bool], SensorEntityDescription] = {
    (Units.C, False, False): SensorEntityDescription(
        key=f"{Units.C}_{False}_{False}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.KWH, False, True): SensorEntityDescription(
        key=f"{Units.KWH}_{False}_{True}",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.KWH, False, False): SensorEntityDescription(
        key=f"{Units.KWH}_{False}_{False}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    (Units.KWH, True, False): SensorEntityDescription(
        key=f"{Units.KWH}_{True}_{False}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    (Units.V, False, False): SensorEntityDescription(
        key=f"{Units.V}_{False}_{False}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.A, False, False): SensorEntityDescription(
        key=f"{Units.A}_{False}_{False}",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.W, False, False): SensorEntityDescription(
        key=f"{Units.W}_{False}_{False}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.PERCENT, False, False): SensorEntityDescription(
        key=f"{Units.PERCENT}_{False}_{False}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.HZ, False, False): SensorEntityDescription(
        key=f"{Units.HZ}_{False}_{False}",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (Units.NONE, False, False): SensorEntityDescription(
        key=f"{Units.NONE}_{False}_{False}",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolaxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Entry setup."""
    coordinator = entry.runtime_data.coordinator
    api = coordinator.api
    resp = cast(InverterResponse, coordinator.data)
    serial = resp.serial_number
    version = resp.version
    entities: list[InverterSensorEntity] = []
    last_reset = dt_util.start_of_local_day()
    for sensor, (idx, measurement) in api.inverter.sensor_map().items():
        description = SENSOR_DESCRIPTIONS[
            (measurement.unit, measurement.is_monotonic, measurement.storage)
        ]

        uid = f"{serial}-{idx}"
        entity = InverterSensorEntity(
            coordinator,
            api.inverter.manufacturer,
            uid,
            serial,
            version,
            sensor,
            description.native_unit_of_measurement,
            description.state_class,
            description.device_class,
            last_reset if measurement.resets_daily else None,
        )
        entities.append(entity)
    async_add_entities(entities)


class InverterSensorEntity(CoordinatorEntity[SolaxDataUpdateCoordinator], SensorEntity):
    """Class for a sensor."""

    def __init__(
        self,
        coordinator: SolaxDataUpdateCoordinator,
        manufacturer: str,
        uid: str,
        serial: str,
        version: str,
        key: str,
        unit: str | None,
        state_class: SensorStateClass | str | None,
        device_class: SensorDeviceClass | None,
        last_reset: datetime | None,
    ) -> None:
        """Initialize an inverter sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = uid
        self._attr_name = f"{manufacturer} {serial} {key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_last_reset = last_reset
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            name=f"{manufacturer} {serial}",
            sw_version=version,
        )
        self.key = key

    def _handle_coordinator_update(self) -> None:
        """Reset at midnight."""
        match self.coordinator.data:
            case Reset(start_of_local_day):
                if self.last_reset is None:
                    return

                self._attr_last_reset = start_of_local_day

        self.async_write_ha_state()

    @property
    def native_value(self):
        """State of this inverter attribute."""
        match self.coordinator.data:
            case Reset(_):
                return 0
            case InverterResponse(data):
                return data[self.key]
