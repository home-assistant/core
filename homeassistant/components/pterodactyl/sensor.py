"""Sensor platform of the Pterodactyl integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PterodactylConfigEntry, PterodactylCoordinator, PterodactylData
from .entity import PterodactylEntity

KEY_CPU_UTILIZATION = "cpu_utilization"
KEY_CPU_LIMIT = "cpu_limit"
KEY_MEMORY_USAGE = "memory_usage"
KEY_MEMORY_LIMIT = "memory_limit"
KEY_DISK_USAGE = "disk_usage"
KEY_DISK_LIMIT = "disk_limit"
KEY_NETWORK_INBOUND = "network_inbound"
KEY_NETWORK_OUTBOUND = "network_outbound"
KEY_UPTIME = "uptime"

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PterodactylSensorEntityDescription(SensorEntityDescription):
    """Class describing Pterodactyl sensor entities."""

    value_fn: Callable[[PterodactylData], StateType]


SENSOR_DESCRIPTIONS = [
    PterodactylSensorEntityDescription(
        key=KEY_CPU_UTILIZATION,
        translation_key=KEY_CPU_UTILIZATION,
        value_fn=lambda data: data.cpu_utilization,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_CPU_LIMIT,
        translation_key=KEY_CPU_LIMIT,
        value_fn=lambda data: data.cpu_limit,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_MEMORY_USAGE,
        translation_key=KEY_MEMORY_USAGE,
        value_fn=lambda data: data.memory_usage,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_MEMORY_LIMIT,
        translation_key=KEY_MEMORY_LIMIT,
        value_fn=lambda data: data.memory_limit,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_DISK_USAGE,
        translation_key=KEY_DISK_USAGE,
        value_fn=lambda data: data.disk_usage,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_DISK_LIMIT,
        translation_key=KEY_DISK_LIMIT,
        value_fn=lambda data: data.disk_limit,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_NETWORK_INBOUND,
        translation_key=KEY_NETWORK_INBOUND,
        value_fn=lambda data: data.network_inbound,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_NETWORK_OUTBOUND,
        translation_key=KEY_NETWORK_OUTBOUND,
        value_fn=lambda data: data.network_outbound,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_UPTIME,
        translation_key=KEY_UPTIME,
        value_fn=lambda data: data.uptime,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PterodactylConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pterodactyl sensor platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        PterodactylSensorEntity(coordinator, identifier, description, config_entry)
        for identifier in coordinator.api.identifiers
        for description in SENSOR_DESCRIPTIONS
    )


class PterodactylSensorEntity(PterodactylEntity, SensorEntity):
    """Representation of a Pterodactyl sensor base entity."""

    entity_description: PterodactylSensorEntityDescription

    def __init__(
        self,
        coordinator: PterodactylCoordinator,
        identifier: str,
        description: PterodactylSensorEntityDescription,
        config_entry: PterodactylConfigEntry,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator, identifier, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.game_server_data.uuid}_{description.key}"
        self._update_properties()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_properties()
        self.async_write_ha_state()

    @callback
    def _update_properties(self) -> None:
        """Update sensor properties."""
        self._attr_native_value = self.entity_description.value_fn(
            self.game_server_data
        )
