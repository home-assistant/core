"""Base entity for IronOS integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL_NUMBER, CONF_SW_VERSION, MANUFACTURER, MODEL
from .coordinator import IronOSLiveDataCoordinator


class IronOSBaseEntity(CoordinatorEntity[IronOSLiveDataCoordinator]):
    """Base IronOS entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IronOSLiveDataCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id

        serial_number = None
        if coordinator.config_entry.data.get(CONF_SERIAL_NUMBER):
            serial_number = f"{coordinator.config_entry.data.get(CONF_SERIAL_NUMBER)} DeviceID:{coordinator.config_entry.data.get(CONF_DEVICE_ID)}"

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Pinecil",
            sw_version=coordinator.config_entry.data.get(CONF_SW_VERSION),
            serial_number=serial_number,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.device._client.is_connected  # noqa: SLF001
