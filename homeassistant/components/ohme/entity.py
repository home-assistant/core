"""Base class for entities."""

from collections.abc import Callable
from dataclasses import dataclass

from ohme import OhmeApiClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OhmeBaseCoordinator


@dataclass(frozen=True)
class OhmeEntityDescription(EntityDescription):
    """Class describing Ohme entities."""

    is_supported_fn: Callable[[OhmeApiClient], bool] = lambda _: True
    available_fn: Callable[[OhmeApiClient], bool] = lambda _: True


class OhmeEntity(CoordinatorEntity[OhmeBaseCoordinator]):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True
    entity_description: OhmeEntityDescription

    def __init__(
        self,
        coordinator: OhmeBaseCoordinator,
        entity_description: OhmeEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        client = coordinator.client
        self._attr_unique_id = f"{client.serial}_{entity_description.key}"

        device_info = client.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.serial)},
            name=device_info["name"],
            manufacturer="Ohme",
            model=device_info["model"],
            sw_version=device_info["sw_version"],
            serial_number=client.serial,
        )

    @property
    def available(self) -> bool:
        """Return if charger reporting as online."""
        return (
            super().available
            and self.coordinator.client.available
            and self.entity_description.available_fn(self.coordinator.client)
        )
