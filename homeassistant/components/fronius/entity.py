"""Support for Fronius devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class FroniusEntityDescription(EntityDescription):
    """Base class for Fronius entity descriptions."""

    response_key: str | None = None


if TYPE_CHECKING:
    from .coordinator import FroniusCoordinatorBase


class _FroniusEntity(CoordinatorEntity["FroniusCoordinatorBase"], Entity):
    """Defines a Fronius coordinator entity."""

    entity_description: FroniusEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        description: FroniusEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.response_key = description.response_key or description.key
        self.solar_net_id = solar_net_id
        self._set_entity_value()
        self._attr_translation_key = description.key

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator.

        Subclasses must implement.

        Raises KeyError if not included in latest update.
        """

        raise NotImplementedError

    def _set_entity_value(self) -> None:
        """Set the entity value correctly based on the platform."""

        raise NotImplementedError
