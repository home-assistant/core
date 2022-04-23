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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PureEnergieData, PureEnergieDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class PureEnergieSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PureEnergieData], int | float]


@dataclass
class PureEnergieSensorEntityDescription(
    SensorEntityDescription, PureEnergieSensorEntityDescriptionMixin
):
    """Describes a Pure Energie sensor entity."""


SENSORS: tuple[PureEnergieSensorEntityDescription, ...] = (
    PureEnergieSensorEntityDescription(
        key="power_flow",
        name="Power Flow",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.smartbridge.power_flow,
    ),
    PureEnergieSensorEntityDescription(
        key="energy_consumption_total",
        name="Energy Consumption",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.smartbridge.energy_consumption_total,
    ),
    PureEnergieSensorEntityDescription(
        key="energy_production_total",
        name="Energy Production",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.smartbridge.energy_production_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Pure Energie Sensors based on a config entry."""
    async_add_entities(
        PureEnergieSensorEntity(
            coordinator=hass.data[DOMAIN][entry.entry_id],
            description=description,
            entry=entry,
        )
        for description in SENSORS
    )


class PureEnergieSensorEntity(
    CoordinatorEntity[PureEnergieDataUpdateCoordinator], SensorEntity
):
    """Defines an Pure Energie sensor."""

    entity_description: PureEnergieSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PureEnergieDataUpdateCoordinator,
        description: PureEnergieSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Pure Energie sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_id = f"{SENSOR_DOMAIN}.pem_{description.key}"
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.device.n2g_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.device.n2g_id)},
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            sw_version=coordinator.data.device.firmware,
            manufacturer=coordinator.data.device.manufacturer,
            model=coordinator.data.device.model,
            name=entry.title,
        )

    @property
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
