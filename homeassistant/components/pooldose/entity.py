"""Base entity for Seko Pooldose integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PooldoseCoordinator


def device_info(info: dict | None, unique_id: str) -> DeviceInfo:
    """Create device info for PoolDose devices."""
    if info is None:
        info = {}

    api_version = info.get("API_VERSION", "").removesuffix("/")

    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL") or None,
        model_id=info.get("MODEL_ID") or None,
        name=info.get("NAME") or None,
        serial_number=unique_id,
        sw_version=(
            f"{info.get('FW_VERSION')} (SW v{info.get('SW_VERSION')}, API {api_version})"
            if info.get("FW_VERSION") and info.get("SW_VERSION") and api_version
            else None
        ),
        hw_version=info.get("FW_CODE") or None,
        connections=(
            {(CONNECTION_NETWORK_MAC, str(info["MAC"]))} if info.get("MAC") else set()
        ),
        configuration_url=(
            f"http://{info['IP']}/index.html" if info.get("IP") else None
        ),
    )


class PooldoseEntity(CoordinatorEntity[PooldoseCoordinator]):
    """Base class for all PoolDose entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_properties: dict[str, Any],
        entity_description: EntityDescription,
    ) -> None:
        """Initialize PoolDose entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{serial_number}_{entity_description.key}"
        self._attr_device_info = device_info(device_properties, serial_number)

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )

    def get_data(self) -> list | tuple | None:
        """Get data for this entity, only if available."""
        if not self.available:
            return None
        return self.coordinator.data.get(self.entity_description.key)
