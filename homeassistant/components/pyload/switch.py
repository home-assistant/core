"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyloadapi.api import PyLoadAPI

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PyLoadConfigEntry
from .const import DOMAIN, MANUFACTURER, SERVICE_NAME
from .coordinator import PyLoadCoordinator


class PyLoadSwitch(StrEnum):
    """PyLoad Switch Entities."""

    PAUSE_RESUME_QUEUE = "download"
    RECONNECT = "reconnect"


@dataclass(kw_only=True, frozen=True)
class PyLoadSwitchEntityDescription(SwitchEntityDescription):
    """Describes pyLoad switch entity."""

    turn_on_fn: Callable[[PyLoadAPI], Awaitable[Any]]
    turn_off_fn: Callable[[PyLoadAPI], Awaitable[Any]]
    toggle_fn: Callable[[PyLoadAPI], Awaitable[Any]]


SENSOR_DESCRIPTIONS: tuple[PyLoadSwitchEntityDescription, ...] = (
    PyLoadSwitchEntityDescription(
        key=PyLoadSwitch.PAUSE_RESUME_QUEUE,
        translation_key=PyLoadSwitch.PAUSE_RESUME_QUEUE,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.unpause(),
        turn_off_fn=lambda api: api.pause(),
        toggle_fn=lambda api: api.toggle_pause(),
    ),
    PyLoadSwitchEntityDescription(
        key=PyLoadSwitch.RECONNECT,
        translation_key=PyLoadSwitch.RECONNECT,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.toggle_reconnect(),
        turn_off_fn=lambda api: api.toggle_reconnect(),
        toggle_fn=lambda api: api.toggle_reconnect(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pyLoad sensors."""

    coordinator = entry.runtime_data

    async_add_entities(
        PyLoadSwitchEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PyLoadSwitchEntity(CoordinatorEntity[PyLoadCoordinator], SwitchEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True
    entity_description: PyLoadSwitchEntityDescription

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: PyLoadSwitchEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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
            sw_version=coordinator.version,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return getattr(self.coordinator.data, self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.turn_on_fn(self.coordinator.pyload)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.turn_off_fn(self.coordinator.pyload)
        await self.coordinator.async_refresh()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        await self.entity_description.toggle_fn(self.coordinator.pyload)
        await self.coordinator.async_refresh()
