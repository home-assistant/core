"""Arve base entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from asyncarve import ArveSensProData

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ArveCoordinator


@dataclass(frozen=True, kw_only=True)
class ArveDeviceEntityDescription(SensorEntityDescription):
    """Describes Arve device entity."""

    value_fn: Callable[[ArveSensProData], float | int]


class ArveDeviceEntity(CoordinatorEntity[ArveCoordinator]):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self, coordinator: ArveCoordinator, description: ArveDeviceEntityDescription
    ) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self._entry = coordinator.config_entry
        self.arve = coordinator.arve
        self.coordinator = coordinator

        self.entity_description = description
        self.trans_key = str(self.entity_description.translation_key)
        self.sn = coordinator.arve.device_sn
        self._attr_unique_id = "_".join(
            [
                self.sn,
                self.trans_key,
            ]
        )

        self.name = description.key
