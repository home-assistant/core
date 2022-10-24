"""Support for LaMetric selects."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from demetriek import BrightnessMode, Device, LaMetricDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler


@dataclass
class LaMetricEntityDescriptionMixin:
    """Mixin values for LaMetric entities."""

    current_fn: Callable[[Device], str]
    select_fn: Callable[[LaMetricDevice, str], Awaitable[Any]]


@dataclass
class LaMetricSelectEntityDescription(
    SelectEntityDescription, LaMetricEntityDescriptionMixin
):
    """Class describing LaMetric select entities."""


SELECTS = [
    LaMetricSelectEntityDescription(
        key="brightness_mode",
        name="Brightness mode",
        icon="mdi:brightness-auto",
        entity_category=EntityCategory.CONFIG,
        device_class="lametric__brightness_mode",
        options=["auto", "manual"],
        current_fn=lambda device: device.display.brightness_mode.value,
        select_fn=lambda api, opt: api.display(brightness_mode=BrightnessMode(opt)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaMetric select based on a config entry."""
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LaMetricSelectEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SELECTS
    )


class LaMetricSelectEntity(LaMetricEntity, SelectEntity):
    """Representation of a LaMetric select."""

    entity_description: LaMetricSelectEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricSelectEntityDescription,
    ) -> None:
        """Initiate LaMetric Select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @lametric_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.lametric, option)
        await self.coordinator.async_request_refresh()
