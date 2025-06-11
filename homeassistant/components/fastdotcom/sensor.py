"""Sensor platform for the Fast.com integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator


@dataclass(frozen=True)
class FastdotcomSensorEntityDescription(SensorEntityDescription):
    """Describes Fast.com sensor entities."""

    value: Callable[[float], float] = lambda val: round(val, 2)


SENSOR_TYPES: tuple[FastdotcomSensorEntityDescription, ...] = (
    FastdotcomSensorEntityDescription(
        key="download_speed",
        name="Download Speed",
        translation_key="download_speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FastdotcomSensorEntityDescription(
        key="upload_speed",
        name="Upload Speed",
        translation_key="upload_speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FastdotcomSensorEntityDescription(
        key="unloaded_ping",
        name="Unloaded Ping",
        translation_key="unloaded_ping",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FastdotcomSensorEntityDescription(
        key="loaded_ping",
        name="Loaded Ping",
        translation_key="loaded_ping",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FastdotcomSensorEntityDescription(
        key="success",
        name="Success",
        translation_key="success",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda val: val,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FastdotcomConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fast.com sensors from a config entry."""
    coordinator = entry.runtime_data
    entry_id = entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=DEFAULT_NAME,
        manufacturer=DEFAULT_NAME,
        model="Speed Test Integration",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://fast.com/",
    )

    entities = [
        FastdotcomSensor(entry_id, coordinator, description, device_info)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class FastdotcomSensor(
    CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity
):
    """Representation of a Fast.com sensor."""

    entity_description: FastdotcomSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        coordinator: FastdotcomDataUpdateCoordinator,
        description: FastdotcomSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize a Fast.com sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        """Return native value for entity."""
        if not self.coordinator.data:
            return None

        data = self.coordinator.data.get(self.entity_description.key)
        if data is None:
            return None

        return self.entity_description.value(data)
