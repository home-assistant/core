"""Support for Pure Energie sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PureEnergieConfigEntry,
    PureEnergieData,
    PureEnergieDataUpdateCoordinator,
)


@dataclass(frozen=True, kw_only=True)
class PureEnergieSensorEntityDescription(SensorEntityDescription):
    """Describes a Pure Energie sensor entity."""

    value_fn: Callable[[PureEnergieData], int | float]


SENSORS: tuple[PureEnergieSensorEntityDescription, ...] = (
    PureEnergieSensorEntityDescription(
        key="power_flow",
        translation_key="power_flow",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.smartbridge.power_flow,
    ),
    PureEnergieSensorEntityDescription(
        key="energy_consumption_total",
        translation_key="energy_consumption_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.smartbridge.energy_consumption_total,
    ),
    PureEnergieSensorEntityDescription(
        key="energy_production_total",
        translation_key="energy_production_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.smartbridge.energy_production_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PureEnergieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pure Energie Sensors based on a config entry."""
    async_add_entities(
        PureEnergieSensorEntity(
            description=description,
            entry=entry,
        )
        for description in SENSORS
    )


class PureEnergieSensorEntity(
    CoordinatorEntity[PureEnergieDataUpdateCoordinator], SensorEntity
):
    """Defines an Pure Energie sensor."""

    _attr_has_entity_name = True
    entity_description: PureEnergieSensorEntityDescription

    def __init__(
        self,
        *,
        description: PureEnergieSensorEntityDescription,
        entry: PureEnergieConfigEntry,
    ) -> None:
        """Initialize Pure Energie sensor."""
        super().__init__(coordinator=entry.runtime_data)
        self.entity_id = f"{SENSOR_DOMAIN}.pem_{description.key}"
        self.entity_description = description
        self._attr_unique_id = (
            f"{entry.runtime_data.data.device.n2g_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.runtime_data.data.device.n2g_id)},
            configuration_url=f"http://{entry.runtime_data.config_entry.data[CONF_HOST]}",
            sw_version=entry.runtime_data.data.device.firmware,
            manufacturer=entry.runtime_data.data.device.manufacturer,
            model=entry.runtime_data.data.device.model,
            name=entry.title,
        )

    @property
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
