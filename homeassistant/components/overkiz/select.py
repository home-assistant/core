"""Support for Overkiz select."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Awaitable

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity


@dataclass
class OverkizSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    options: list[str]
    select_option: Callable[[str, Callable], Awaitable]


@dataclass
class OverkizSelectDescription(SelectEntityDescription, OverkizSelectDescriptionMixin):
    """Class to describe an Overkiz select entity."""


SELECT_DESCRIPTIONS: list[OverkizSelectDescription] = [
    OverkizSelectDescription(
        key=OverkizState.CORE_OPEN_CLOSED_PEDESTRIAN,
        name="Position",
        icon="mdi:content-save-cog",
        options=[
            OverkizCommandParam.OPEN,
            OverkizCommandParam.PEDESTRIAN,
            OverkizCommandParam.CLOSED,
        ],
        select_option=lambda option, execute_command: execute_command(
            {
                OverkizCommandParam.CLOSED: OverkizCommand.CLOSE,
                OverkizCommandParam.OPEN: OverkizCommand.OPEN,
                OverkizCommandParam.PEDESTRIAN: OverkizCommand.SET_PEDESTRIAN_POSITION,
            }[option]
        ),
    ),
    OverkizSelectDescription(
        key=OverkizState.IO_MEMORIZED_SIMPLE_VOLUME,
        name="Memorized Simple Volume",
        icon="mdi:volume-high",
        options=[OverkizCommandParam.STANDARD, OverkizCommandParam.HIGHEST],
        select_option=lambda option, execute_command: execute_command(
            OverkizCommand.SET_MEMORIZED_SIMPLE_VOLUME, option
        ),
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Overkiz select from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[OverkizSelect] = []

    key_supported_states = {
        description.key: description for description in SELECT_DESCRIPTIONS
    }

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        for state in device.definition.states:
            if description := key_supported_states.get(state.qualified_name):
                entities.append(
                    OverkizSelect(
                        device.device_url,
                        data.coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class OverkizSelect(OverkizDescriptiveEntity, SelectEntity):
    """Representation of an Overkiz Select entity."""

    entity_description: OverkizSelectDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if state := self.device.states.get(self.entity_description.key):
            return state.value

        return None

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_option(
            option, self.executor.async_execute_command
        )
