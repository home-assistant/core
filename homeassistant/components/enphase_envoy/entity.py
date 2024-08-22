"""Support for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EnphaseUpdateCoordinator

if TYPE_CHECKING:
    from pyenphase import EnvoyData

    from homeassistant.helpers.entity import EntityDescription


class EnvoyBaseEntity(CoordinatorEntity[EnphaseUpdateCoordinator]):
    """Defines a base envoy entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Init the Enphase base entity."""
        self.entity_description = description
        serial_number = coordinator.envoy.serial_number
        assert serial_number is not None
        self.envoy_serial_num = serial_number
        super().__init__(coordinator)

    @property
    def data(self) -> EnvoyData:
        """Return envoy data."""
        data = self.coordinator.envoy.data
        assert data is not None
        return data
