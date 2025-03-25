"""Sensor platform of the Pterodactyl integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_conversion import DurationConverter, InformationConverter

from .coordinator import PterodactylConfigEntry, PterodactylCoordinator, PterodactylData
from .entity import PterodactylEntity

KEY_CPU_UTILIZATION = "cpu_utilization"
KEY_MEMORY_UTILIZATION = "memory_utilization"
KEY_DISK_UTILIZATION = "disk_utilization"
KEY_NETWORK_INBOUND = "network_inbound"
KEY_NETWORK_OUTBOUND = "network_outbound"
KEY_UPTIME = "uptime"

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PterodactylSensorEntityDescription(SensorEntityDescription):
    """Class describing Pterodactyl sensor entities."""

    value_fn: Callable[[PterodactylData], StateType]
    attributes_fn: Callable[[PterodactylData], dict[str, Any]] | None


def get_extra_state_attributes_cpu(
    data: PterodactylData,
) -> dict[str, list[str]]:
    """Return CPU limit as extra state attribute."""
    extra_state_attributes: dict[str, Any] = {}

    extra_state_attributes["cpu_limit"] = data.cpu_limit

    return extra_state_attributes


def get_extra_state_attributes_memory(
    data: PterodactylData,
) -> dict[str, list[str]]:
    """Return memory usage and limit as extra state attributes."""
    extra_state_attributes: dict[str, Any] = {}

    extra_state_attributes["memory_usage"] = round(
        InformationConverter.convert(
            data.memory_usage, UnitOfInformation.BYTES, UnitOfInformation.MEGABYTES
        )
    )
    extra_state_attributes["memory_limit"] = round(
        InformationConverter.convert(
            data.memory_limit, UnitOfInformation.BYTES, UnitOfInformation.MEGABYTES
        )
    )

    return extra_state_attributes


def get_extra_state_attributes_disk(
    data: PterodactylData,
) -> dict[str, list[str]]:
    """Return disk usage and limit as extra state attributes."""
    extra_state_attributes: dict[str, Any] = {}

    extra_state_attributes["disk_usage"] = round(
        InformationConverter.convert(
            data.disk_usage, UnitOfInformation.BYTES, UnitOfInformation.MEGABYTES
        )
    )
    extra_state_attributes["disk_limit"] = round(
        InformationConverter.convert(
            data.disk_limit, UnitOfInformation.BYTES, UnitOfInformation.MEGABYTES
        )
    )

    return extra_state_attributes


SENSOR_DESCRIPTIONS = [
    PterodactylSensorEntityDescription(
        key=KEY_CPU_UTILIZATION,
        translation_key=KEY_CPU_UTILIZATION,
        value_fn=lambda data: data.cpu_utilization,
        attributes_fn=get_extra_state_attributes_cpu,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_MEMORY_UTILIZATION,
        translation_key=KEY_MEMORY_UTILIZATION,
        value_fn=lambda data: ((data.memory_usage / data.memory_limit) * 100),
        attributes_fn=get_extra_state_attributes_memory,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_DISK_UTILIZATION,
        translation_key=KEY_DISK_UTILIZATION,
        value_fn=lambda data: ((data.disk_usage / data.disk_limit) * 100),
        attributes_fn=get_extra_state_attributes_disk,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_NETWORK_INBOUND,
        translation_key=KEY_NETWORK_INBOUND,
        value_fn=lambda data: InformationConverter.convert(
            data.network_inbound, UnitOfInformation.BYTES, UnitOfInformation.KILOBYTES
        ),
        attributes_fn=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_NETWORK_OUTBOUND,
        translation_key=KEY_NETWORK_OUTBOUND,
        value_fn=lambda data: InformationConverter.convert(
            data.network_outbound, UnitOfInformation.BYTES, UnitOfInformation.KILOBYTES
        ),
        attributes_fn=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PterodactylSensorEntityDescription(
        key=KEY_UPTIME,
        translation_key=KEY_UPTIME,
        value_fn=lambda data: DurationConverter.convert(
            data.uptime, UnitOfTime.SECONDS, UnitOfTime.MINUTES
        ),
        attributes_fn=None,
        native_unit_of_measurement=UnitOfTime.MINUTES,
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
        [
            PterodactylSensorEntity(coordinator, identifier, description, config_entry)
            for identifier in coordinator.api.identifiers
            for description in SENSOR_DESCRIPTIONS
        ]
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

        if func := self.entity_description.attributes_fn:
            self._attr_extra_state_attributes = func(self.game_server_data)
