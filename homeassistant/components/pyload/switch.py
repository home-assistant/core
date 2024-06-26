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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PyLoadConfigEntry
from .coordinator import PyLoadCoordinator
from .entity import BasePyLoadEntity


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


class PyLoadSwitchEntity(BasePyLoadEntity, SwitchEntity):
    """Representation of a pyLoad sensor."""

    entity_description: PyLoadSwitchEntityDescription

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: PyLoadSwitchEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

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
