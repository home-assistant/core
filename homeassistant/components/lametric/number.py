"""Support for LaMetric numbers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from demetriek import Device, LaMetricDevice

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity


@dataclass
class LaMetricEntityDescriptionMixin:
    """Mixin values for LaMetric entities."""

    value_fn: Callable[[Device], int | None]
    set_value_fn: Callable[[LaMetricDevice, float], Awaitable[Any]]


@dataclass
class LaMetricNumberEntityDescription(
    NumberEntityDescription, LaMetricEntityDescriptionMixin
):
    """Class describing LaMetric number entities."""


NUMBERS = [
    LaMetricNumberEntityDescription(
        key="volume",
        name="Volume",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        value_fn=lambda device: device.audio.volume,
        set_value_fn=lambda api, volume: api.audio(volume=int(volume)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaMetric number based on a config entry."""
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LaMetricNumberEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in NUMBERS
    )


class LaMetricNumberEntity(LaMetricEntity, NumberEntity):
    """Representation of a LaMetric number."""

    entity_description: LaMetricNumberEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricNumberEntityDescription,
    ) -> None:
        """Initiate Plugwise Number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the present setpoint value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Change to the new setpoint value."""
        await self.entity_description.set_value_fn(self.coordinator.lametric, value)
        await self.coordinator.async_request_refresh()
