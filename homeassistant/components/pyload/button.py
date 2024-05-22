"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from pyloadapi.api import PyLoadAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PyLoadConfigEntry
from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import PyLoadCoordinator
from .util import api_url

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class PyLoadButtonEntityDescription(ButtonEntityDescription):
    """Describes pyLoad switch entity."""

    press_fn: Callable[[PyLoadAPI], Awaitable[Any]]


class PyLoadButtonEntity(StrEnum):
    """PyLoad Switch Entities."""

    ABORT_DOWNLOADS = "abort_downloads"
    RESTART_FAILED = "restart_failed"
    DELETE_FINISHED = "delete_finished"
    RESTART = "restart"


SENSOR_DESCRIPTIONS: dict[str, PyLoadButtonEntityDescription] = {
    PyLoadButtonEntity.ABORT_DOWNLOADS: PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.ABORT_DOWNLOADS,
        translation_key=PyLoadButtonEntity.ABORT_DOWNLOADS,
        press_fn=lambda api: api.stop_all_downloads(),
    ),
    PyLoadButtonEntity.RESTART_FAILED: PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.RESTART_FAILED,
        translation_key=PyLoadButtonEntity.RESTART_FAILED,
        press_fn=lambda api: api.restart_failed(),
    ),
    PyLoadButtonEntity.DELETE_FINISHED: PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.DELETE_FINISHED,
        translation_key=PyLoadButtonEntity.DELETE_FINISHED,
        press_fn=lambda api: api.delete_finished(),
    ),
    PyLoadButtonEntity.RESTART: PyLoadButtonEntityDescription(
        key=PyLoadButtonEntity.RESTART,
        translation_key=PyLoadButtonEntity.RESTART,
        press_fn=lambda api: api.restart(),
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        PyLoadBinarySensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS.values()
    )


class PyLoadBinarySensor(CoordinatorEntity, ButtonEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True
    entity_description: PyLoadButtonEntityDescription
    coordinator: PyLoadCoordinator

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: PyLoadButtonEntityDescription,
        entry: PyLoadConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            configuration_url=api_url(entry.data),
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key=DOMAIN,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.pyload)
