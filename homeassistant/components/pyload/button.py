"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyloadapi.api import PyLoadAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PyLoadConfigEntry
from .const import DOMAIN, MANUFACTURER, SERVICE_NAME
from .coordinator import PyLoadCoordinator


@dataclass(kw_only=True, frozen=True)
class PyLoadButtonEntityDescription(ButtonEntityDescription):
    """Describes pyLoad button entity."""

    press_fn: Callable[[PyLoadAPI], Awaitable[Any]]


class PyLoadButtonEntity(StrEnum):
    """PyLoad button Entities."""

    ABORT_DOWNLOADS = "abort_downloads"
    RESTART_FAILED = "restart_failed"
    DELETE_FINISHED = "delete_finished"
    RESTART = "restart"


SENSOR_DESCRIPTIONS: tuple[PyLoadButtonEntityDescription, ...] = (
    PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.ABORT_DOWNLOADS,
        translation_key=PyLoadButtonEntity.ABORT_DOWNLOADS,
        press_fn=lambda api: api.stop_all_downloads(),
    ),
    PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.RESTART_FAILED,
        translation_key=PyLoadButtonEntity.RESTART_FAILED,
        press_fn=lambda api: api.restart_failed(),
    ),
    PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.DELETE_FINISHED,
        translation_key=PyLoadButtonEntity.DELETE_FINISHED,
        press_fn=lambda api: api.delete_finished(),
    ),
    PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.RESTART,
        translation_key=PyLoadButtonEntity.RESTART,
        press_fn=lambda api: api.restart(),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        PyLoadBinarySensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PyLoadBinarySensor(CoordinatorEntity[PyLoadCoordinator], ButtonEntity):
    """Representation of a pyLoad button."""

    _attr_has_entity_name = True
    entity_description: PyLoadButtonEntityDescription

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: PyLoadButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=SERVICE_NAME,
            configuration_url=coordinator.pyload.api_url,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            translation_key=DOMAIN,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.pyload)
