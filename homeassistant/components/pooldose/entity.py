"""Base entity for Seko Pooldose integration."""

from __future__ import annotations

from pooldose.client import PooldoseClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PooldoseCoordinator


class PooldoseEntity(CoordinatorEntity["PooldoseCoordinator"]):
    """Base class for all Pooldose entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        client: PooldoseClient,
        translation_key: str,
        key: str,
        serialnumber: str,
        device_info_dict: DeviceInfo,
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize the base Pooldose entity."""
        super().__init__(coordinator)
        self._client = client
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_device_info = device_info_dict
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
