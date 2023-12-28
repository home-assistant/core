"""Renson ventilation unit time."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from _collections_abc import Callable
from renson_endura_delta.field_enum import DAYTIME_FIELD, NIGHTTIME_FIELD, FieldEnum
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonCoordinator, RensonData
from .const import DOMAIN
from .entity import RensonEntity


@dataclass
class RensonTimeEntityDescriptionMixin:
    """Mixin for required keys."""

    field: FieldEnum
    action_fn: Callable[[RensonVentilation, str], None]


@dataclass
class RensonTimeEntityDescription(
    TimeEntityDescription, RensonTimeEntityDescriptionMixin
):
    """Class describing Renson time entity."""


ENTITY_DESCRIPTIONS: tuple[RensonTimeEntityDescription, ...] = (
    RensonTimeEntityDescription(
        key="day_time",
        entity_category=EntityCategory.CONFIG,
        translation_key="day_time",
        action_fn=lambda api, time: api.set_day_time(time),
        field=DAYTIME_FIELD,
        has_entity_name=True,
    ),
    RensonTimeEntityDescription(
        key="night_time",
        translation_key="night_time",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda api, time: api.set_night_time(time),
        field=NIGHTTIME_FIELD,
        has_entity_name=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson time platform."""

    data: RensonData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        RensonTime(description, data.api, data.coordinator)
        for description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities, True)


class RensonTime(RensonEntity, TimeEntity):
    """Representation of a Renson time entity."""

    entity_description: RensonTimeEntityDescription

    def __init__(
        self,
        description: RensonTimeEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        all_data = self.coordinator.data

        value = self.api.get_field_value(all_data, self.entity_description.field.name)

        self._attr_native_value = datetime.strptime(
            value,
            "%H:%M",
        ).time()

        super()._handle_coordinator_update()

    def set_value(self, value: time) -> None:
        """Triggers the action."""

        string_value = value.strftime("%H:%M")
        self.entity_description.action_fn(self.api, string_value)
