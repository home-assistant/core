"""Base class for entities."""

from typing import Any

from ohme import OhmeApiClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OhmeCoordinator


class OhmeEntity(CoordinatorEntity[OhmeCoordinator]):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OhmeCoordinator,
        client: OhmeApiClient,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._client = client
        self._attr_translation_key = entity_description.key
        self._attr_unique_id = f"{self._client.serial}_{self._attr_translation_key}"

        device_info: dict[str, Any] = client.device_info
        self._attr_device_info = DeviceInfo(
            identifiers=device_info["identifiers"],
            name=device_info["name"],
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
            sw_version=device_info["sw_version"],
            serial_number=device_info["serial_number"],
        )

    @property
    def available(self) -> bool:
        """Return if charger reporting as online."""
        return self._client.available
