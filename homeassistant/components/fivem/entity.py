"""The FiveM entity."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FiveMDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class FiveMEntityDescription(EntityDescription):
    """Describes FiveM entity."""

    extra_attrs: list[str] | None = None


class FiveMEntity(CoordinatorEntity[FiveMDataUpdateCoordinator]):
    """Representation of a FiveM base entity."""

    _attr_has_entity_name = True

    entity_description: FiveMEntityDescription

    def __init__(
        self,
        coordinator: FiveMDataUpdateCoordinator,
        description: FiveMEntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{self.coordinator.unique_id}-{description.key}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.server,
            name=self.coordinator.host,
            sw_version=self.coordinator.version,
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra attributes of the sensor."""
        if self.entity_description.extra_attrs is None:
            return None

        return {
            attr: self.coordinator.data[attr]
            for attr in self.entity_description.extra_attrs
        }
