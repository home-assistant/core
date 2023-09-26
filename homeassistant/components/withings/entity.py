"""Base entity for Withings."""
from __future__ import annotations

from dataclasses import dataclass

from withings_api.common import GetSleepSummaryField, MeasureType, NotifyAppli

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, Measurement
from .coordinator import WithingsDataUpdateCoordinator


@dataclass
class WithingsEntityDescriptionMixin:
    """Mixin for describing withings data."""

    measurement: Measurement
    measure_type: NotifyAppli | GetSleepSummaryField | MeasureType


@dataclass
class WithingsEntityDescription(EntityDescription, WithingsEntityDescriptionMixin):
    """Immutable class for describing withings data."""


class WithingsEntity(Entity):
    """Base class for withings entities."""

    _attr_has_entity_name = True

    def __init__(self, user_id: str) -> None:
        """Initialize the Withings entity."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Withings",
        )


class WithingsCoordinatedEntity(
    WithingsEntity, CoordinatorEntity[WithingsDataUpdateCoordinator]
):
    """Base class for withings entities with description."""

    entity_description: WithingsEntityDescription

    def __init__(
        self,
        coordinator: WithingsDataUpdateCoordinator,
        description: WithingsEntityDescription,
    ) -> None:
        """Initialize the Withings entity."""
        WithingsEntity.__init__(self, str(coordinator.config_entry.unique_id))
        CoordinatorEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"withings_{coordinator.config_entry.unique_id}_{description.measurement.value}"
