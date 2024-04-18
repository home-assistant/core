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
from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import PyLoadCoordinator
from .util import api_url


@dataclass(kw_only=True, frozen=True)
class PyLoadSwitchEntityDescription(SwitchEntityDescription):
    """Describes pyLoad switch entity."""

    turn_on_fn: Callable[[PyLoadAPI], Awaitable[Any]]
    turn_off_fn: Callable[[PyLoadAPI], Awaitable[Any]]
    toggle_fn: Callable[[PyLoadAPI], Awaitable[Any]]


class PyLoadSwitchEntity(StrEnum):
    """PyLoad Switch Entities."""

    PAUSE_RESUME_QUEUE = "download"
    RECONNECT = "reconnect"


SENSOR_DESCRIPTIONS: dict[str, PyLoadSwitchEntityDescription] = {
    PyLoadSwitchEntity.PAUSE_RESUME_QUEUE: PyLoadSwitchEntityDescription(
        key=PyLoadSwitchEntity.PAUSE_RESUME_QUEUE,
        translation_key=PyLoadSwitchEntity.PAUSE_RESUME_QUEUE,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.unpause(),
        turn_off_fn=lambda api: api.pause(),
        toggle_fn=lambda api: api.toggle_pause(),
    ),
    PyLoadSwitchEntity.RECONNECT: PyLoadSwitchEntityDescription(
        key=PyLoadSwitchEntity.RECONNECT,
        translation_key=PyLoadSwitchEntity.RECONNECT,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.toggle_reconnect(),
        turn_off_fn=lambda api: api.toggle_reconnect(),
        toggle_fn=lambda api: api.toggle_reconnect(),
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


class PyLoadBinarySensor(CoordinatorEntity, SwitchEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True
    entity_description: PyLoadSwitchEntityDescription
    coordinator: PyLoadCoordinator

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: PyLoadSwitchEntityDescription,
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

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.coordinator.data[self.entity_description.key]

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
