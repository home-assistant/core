"""The read-only sensors for APsystems local API integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from APsystemsEZ1 import ReturnOutputData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApSystemsDataCoordinator


@dataclass(frozen=True, kw_only=True)
class ApsystemsLocalApiSensorDescription(SensorEntityDescription):
    """Describes Apsystens Inverter sensor entity."""

    value_fn: Callable[[ReturnOutputData], float | None]


SENSORS: tuple[ApsystemsLocalApiSensorDescription, ...] = (
    ApsystemsLocalApiSensorDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p1 + c.p2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="total_power_p1",
        translation_key="total_power_p1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="total_power_p2",
        translation_key="total_power_p2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production",
        translation_key="lifetime_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.te1 + c.te2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production_p1",
        translation_key="lifetime_production_p1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.te1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production_p2",
        translation_key="lifetime_production_p2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.te2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production",
        translation_key="today_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e1 + c.e2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production_p1",
        translation_key="today_production_p1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production_p2",
        translation_key="today_production_p2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    config = config_entry.runtime_data
    device_id = config_entry.unique_id
    assert device_id

    add_entities(
        ApSystemsSensorWithDescription(config, desc, device_id) for desc in SENSORS
    )


class ApSystemsSensorWithDescription(
    CoordinatorEntity[ApSystemsDataCoordinator], SensorEntity
):
    """Base sensor to be used with description."""

    entity_description: ApsystemsLocalApiSensorDescription

    def __init__(
        self,
        coordinator: ApSystemsDataCoordinator,
        entity_description: ApsystemsLocalApiSensorDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            serial_number=device_id,
            manufacturer="APsystems",
            model="EZ1-M",
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
