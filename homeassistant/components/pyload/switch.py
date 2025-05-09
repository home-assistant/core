"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyloadapi import CannotConnect, InvalidAuth, PyLoadAPI

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PyLoadConfigEntry, PyLoadData
from .entity import BasePyLoadEntity

PARALLEL_UPDATES = 1


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
    value_fn: Callable[[PyLoadData], bool]


SENSOR_DESCRIPTIONS: tuple[PyLoadSwitchEntityDescription, ...] = (
    PyLoadSwitchEntityDescription(
        key=PyLoadSwitch.PAUSE_RESUME_QUEUE,
        translation_key=PyLoadSwitch.PAUSE_RESUME_QUEUE,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.unpause(),
        turn_off_fn=lambda api: api.pause(),
        toggle_fn=lambda api: api.toggle_pause(),
        value_fn=lambda data: data.download,
    ),
    PyLoadSwitchEntityDescription(
        key=PyLoadSwitch.RECONNECT,
        translation_key=PyLoadSwitch.RECONNECT,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda api: api.toggle_reconnect(),
        turn_off_fn=lambda api: api.toggle_reconnect(),
        toggle_fn=lambda api: api.toggle_reconnect(),
        value_fn=lambda data: data.reconnect,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(
            self.coordinator.data,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.pyload)
        except CannotConnect as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        except InvalidAuth as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_auth_exception",
            ) from e

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.pyload)
        except CannotConnect as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        except InvalidAuth as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_auth_exception",
            ) from e

        await self.coordinator.async_refresh()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        try:
            await self.entity_description.toggle_fn(self.coordinator.pyload)
        except CannotConnect as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        except InvalidAuth as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_auth_exception",
            ) from e

        await self.coordinator.async_refresh()
