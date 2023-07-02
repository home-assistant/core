"""Plugwise Select component for Home Assistant."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from plugwise import DeviceData, Smile

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


@dataclass
class PlugwiseSelectDescriptionMixin:
    """Mixin values for Plugwise Select entities."""

    command: Callable[[Smile, str, str], Awaitable[Any]]
    value_fn: Callable[[DeviceData], str]
    options_fn: Callable[[DeviceData], list[str]]


@dataclass
class PlugwiseSelectEntityDescription(
    SelectEntityDescription, PlugwiseSelectDescriptionMixin
):
    """Class describing Plugwise Number entities."""


SELECT_TYPES = (
    PlugwiseSelectEntityDescription(
        key="select_schedule",
        translation_key="select_schedule",
        icon="mdi:calendar-clock",
        command=lambda api, loc, opt: api.set_schedule_state(loc, opt, STATE_ON),
        value_fn=lambda data: data["selected_schedule"],
        options_fn=lambda data: data.get("available_schedules"),
    ),
    PlugwiseSelectEntityDescription(
        key="select_regulation_mode",
        translation_key="regulation_mode",
        icon="mdi:hvac",
        entity_category=EntityCategory.CONFIG,
        command=lambda api, loc, opt: api.set_regulation_mode(opt),
        value_fn=lambda data: data["regulation_mode"],
        options_fn=lambda data: data.get("regulation_modes"),
    ),
    PlugwiseSelectEntityDescription(
        key="select_dhw_mode",
        translation_key="dhw_mode",
        icon="mdi:shower",
        entity_category=EntityCategory.CONFIG,
        command=lambda api, loc, opt: api.set_dhw_mode(opt),
        value_fn=lambda data: data["dhw_mode"],
        options_fn=lambda data: data.get("dhw_modes"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile selector from a config entry."""
    coordinator: PlugwiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[PlugwiseSelectEntity] = []
    for device_id, device in coordinator.data.devices.items():
        for description in SELECT_TYPES:
            if (options := description.options_fn(device)) and len(options) > 1:
                entities.append(
                    PlugwiseSelectEntity(coordinator, device_id, description)
                )

    async_add_entities(entities)


class PlugwiseSelectEntity(PlugwiseEntity, SelectEntity):
    """Represent Smile selector."""

    entity_description: PlugwiseSelectEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        entity_description: PlugwiseSelectEntityDescription,
    ) -> None:
        """Initialise the selector."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.value_fn(self.device)

    @property
    def options(self) -> list[str]:
        """Return the selectable entity options."""
        return self.entity_description.options_fn(self.device)

    async def async_select_option(self, option: str) -> None:
        """Change to the selected entity option."""
        await self.entity_description.command(
            self.coordinator.api, self.device["location"], option
        )

        await self.coordinator.async_request_refresh()
