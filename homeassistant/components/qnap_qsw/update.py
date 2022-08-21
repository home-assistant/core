"""Support for the QNAP QSW update."""
from __future__ import annotations

from typing import Final

from aioqsw.const import (
    QSD_DESCRIPTION,
    QSD_FIRMWARE_CHECK,
    QSD_FIRMWARE_INFO,
    QSD_PRODUCT,
    QSD_SYSTEM_BOARD,
    QSD_VERSION,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, QSW_COORD_FW, QSW_UPDATE
from .coordinator import QswFirmwareCoordinator
from .entity import QswFirmwareEntity

UPDATE_TYPES: Final[tuple[UpdateEntityDescription, ...]] = (
    UpdateEntityDescription(
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        key=QSW_UPDATE,
        name="Firmware Update",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW updates from a config_entry."""
    coordinator: QswFirmwareCoordinator = hass.data[DOMAIN][entry.entry_id][
        QSW_COORD_FW
    ]
    async_add_entities(
        QswUpdate(coordinator, description, entry) for description in UPDATE_TYPES
    )


class QswUpdate(QswFirmwareEntity, UpdateEntity):
    """Define a QNAP QSW update."""

    entity_description: UpdateEntityDescription

    def __init__(
        self,
        coordinator: QswFirmwareCoordinator,
        description: UpdateEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = (
            f"{self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT)} {description.name}"
        )
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.entity_description = description

        self._attr_installed_version = self.get_device_value(
            QSD_FIRMWARE_INFO, QSD_VERSION
        )
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attributes."""
        self._attr_latest_version = self.get_device_value(
            QSD_FIRMWARE_CHECK, QSD_VERSION
        )
        self._attr_release_summary = self.get_device_value(
            QSD_FIRMWARE_CHECK, QSD_DESCRIPTION
        )
