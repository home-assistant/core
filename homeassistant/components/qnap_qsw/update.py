"""Support for the QNAP QSW update."""

from __future__ import annotations

from typing import Any, Final

from aioqsw.const import (
    QSD_DESCRIPTION,
    QSD_FIRMWARE_CHECK,
    QSD_FIRMWARE_INFO,
    QSD_VERSION,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QSW_UPDATE
from .coordinator import QnapQswConfigEntry, QswFirmwareCoordinator
from .entity import QswFirmwareEntity

UPDATE_TYPES: Final[tuple[UpdateEntityDescription, ...]] = (
    UpdateEntityDescription(
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        key=QSW_UPDATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QnapQswConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add QNAP QSW updates from a config_entry."""
    coordinator = entry.runtime_data.firmware_coordinator
    async_add_entities(
        QswUpdate(coordinator, description, entry) for description in UPDATE_TYPES
    )


class QswUpdate(QswFirmwareEntity, UpdateEntity):
    """Define a QNAP QSW update."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    entity_description: UpdateEntityDescription

    def __init__(
        self,
        coordinator: QswFirmwareCoordinator,
        description: UpdateEntityDescription,
        entry: QnapQswConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
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

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.coordinator.async_refresh()
        await self.coordinator.qsw.live_update()

        self._attr_installed_version = self.latest_version
        self.async_write_ha_state()
