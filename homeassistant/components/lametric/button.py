"""Support for LaMetric buttons."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from demetriek import LaMetricDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity


@dataclass
class LaMetricButtonEntityDescriptionMixin:
    """Mixin values for LaMetric entities."""

    press_fn: Callable[[LaMetricDevice], Awaitable[Any]]


@dataclass
class LaMetricButtonEntityDescription(
    ButtonEntityDescription, LaMetricButtonEntityDescriptionMixin
):
    """Class describing LaMetric button entities."""


BUTTONS = [
    LaMetricButtonEntityDescription(
        key="app_next",
        name="Next app",
        icon="mdi:arrow-right-bold",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api: api.app_next(),
    ),
    LaMetricButtonEntityDescription(
        key="app_previous",
        name="Previous app",
        icon="mdi:arrow-left-bold",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api: api.app_previous(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaMetric button based on a config entry."""
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LaMetricButtonEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in BUTTONS
    )


class LaMetricButtonEntity(LaMetricEntity, ButtonEntity):
    """Representation of a LaMetric number."""

    entity_description: LaMetricButtonEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    async def async_press(self) -> None:
        """Send out a command to LaMetric."""
        await self.entity_description.press_fn(self.coordinator.lametric)
