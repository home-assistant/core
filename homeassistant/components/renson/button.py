"""Renson ventilation unit buttons."""
from __future__ import annotations

from dataclasses import dataclass

from _collections_abc import Callable
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonCoordinator, RensonData
from .const import DOMAIN
from .entity import RensonEntity


@dataclass
class RensonButtonEntityDescriptionMixin:
    """Action function called on press."""

    action_fn: Callable[[RensonVentilation], None]


@dataclass
class RensonButtonEntityDescription(
    ButtonEntityDescription, RensonButtonEntityDescriptionMixin
):
    """Class describing Renson button entity."""


ENTITY_DESCRIPTIONS: tuple[RensonButtonEntityDescription, ...] = (
    RensonButtonEntityDescription(
        key="sync_time",
        entity_category=EntityCategory.CONFIG,
        translation_key="sync_time",
        action_fn=lambda api: api.sync_time(),
    ),
    RensonButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda api: api.restart_device(),
    ),
    RensonButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda api: api.reset_filter(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson button platform."""

    data: RensonData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        RensonButton(description, data.api, data.coordinator)
        for description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities)


class RensonButton(RensonEntity, ButtonEntity):
    """Representation of a Renson actions."""

    _attr_has_entity_name = True
    entity_description: RensonButtonEntityDescription

    def __init__(
        self,
        description: RensonButtonEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.entity_description = description

    def press(self) -> None:
        """Triggers the action."""
        self.entity_description.action_fn(self.api)
