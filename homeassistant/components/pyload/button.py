"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyloadapi import CannotConnect, InvalidAuth, PyLoadAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PyLoadConfigEntry
from .entity import BasePyLoadEntity

PARALLEL_UPDATES = 1


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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        PyLoadBinarySensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PyLoadBinarySensor(BasePyLoadEntity, ButtonEntity):
    """Representation of a pyLoad button."""

    entity_description: PyLoadButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_fn(self.coordinator.pyload)
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
