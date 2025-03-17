"""Support for LaMetric switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from demetriek import Device, LaMetricDevice

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler


@dataclass(frozen=True, kw_only=True)
class LaMetricSwitchEntityDescription(SwitchEntityDescription):
    """Class describing LaMetric switch entities."""

    available_fn: Callable[[Device], bool] = lambda device: True
    has_fn: Callable[[Device], bool] = lambda device: True
    is_on_fn: Callable[[Device], bool]
    set_fn: Callable[[LaMetricDevice, bool], Awaitable[Any]]


SWITCHES = [
    LaMetricSwitchEntityDescription(
        key="bluetooth",
        translation_key="bluetooth",
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda device: bool(
            device.bluetooth and device.bluetooth.available
        ),
        has_fn=lambda device: bool(device.bluetooth),
        is_on_fn=lambda device: bool(device.bluetooth and device.bluetooth.active),
        set_fn=lambda api, active: api.bluetooth(active=active),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric switch based on a config entry."""
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LaMetricSwitchEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SWITCHES
        if description.has_fn(coordinator.data)
    )


class LaMetricSwitchEntity(LaMetricEntity, SwitchEntity):
    """Representation of a LaMetric switch."""

    entity_description: LaMetricSwitchEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricSwitchEntityDescription,
    ) -> None:
        """Initiate LaMetric Switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @lametric_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.set_fn(self.coordinator.lametric, True)
        await self.coordinator.async_request_refresh()

    @lametric_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.set_fn(self.coordinator.lametric, False)
        await self.coordinator.async_request_refresh()
