"""Base entity for Seko Pooldose integration."""

from __future__ import annotations

from typing import Any

from pooldose.type_definitions import DeviceInfoDict

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PooldoseCoordinator


def device_info(
    info: DeviceInfoDict | None, unique_id: str, mac: str | None = None
) -> DeviceInfo:
    """Create device info for PoolDose devices."""
    if info is None:
        info = {}

    api_version = (info.get("API_VERSION") or "").removesuffix("/")

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
        configuration_url=(
            f"http://{info['IP']}/index.html" if info.get("IP") else None
        ),
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
    )


class PooldoseEntity(CoordinatorEntity[PooldoseCoordinator]):
    """Base class for all PoolDose entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_properties: DeviceInfoDict,
        entity_description: EntityDescription,
        platform_name: str,
    ) -> None:
        """Initialize PoolDose entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.platform_name = platform_name
        self._attr_unique_id = f"{serial_number}_{entity_description.key}"
        self._attr_device_info = device_info(
            device_properties,
            serial_number,
            coordinator.config_entry.data.get(CONF_MAC),
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        if not super().available or self.coordinator.data is None:
            return False
        # Check if the entity type exists in coordinator data
        platform_data = self.coordinator.data.get(self.platform_name, {})
        return (
            isinstance(platform_data, dict)
            and self.entity_description.key in platform_data
        )

    def get_data(self) -> dict[str, Any] | None:
        """Get data for this entity, only if available."""
        if not self.available:
            return None
        platform_data = self.coordinator.data.get(self.platform_name, {})
        if isinstance(platform_data, dict):
            return platform_data.get(self.entity_description.key)
        return None
