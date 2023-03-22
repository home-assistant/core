"""Flame height number sensors."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from intellifire4py.intellifire import IntellifireAPILocal

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntelliFireNumberRequiredKeysMixin:
    """Mixin for required keys."""

    get_value_fn: Callable[[IntellifireAPILocal], int]
    set_value_fn: Callable[[IntellifireAPILocal, int], Awaitable]


@dataclass
class IntelliFireNumberEntityDescription(
    NumberEntityDescription,
    IntelliFireNumberRequiredKeysMixin,
):
    """Describes a sensor entity."""

    mode: NumberMode = NumberMode.AUTO


INTELLIFIRE_NUMBERS: tuple[IntelliFireNumberEntityDescription, ...] = (
    IntelliFireNumberEntityDescription(
        key="flame_control",
        name="Flame control",
        icon="mdi:arrow-expand-vertical",
        mode=NumberMode.SLIDER,
        native_max_value=5,
        native_min_value=1,
        native_step=1,
        get_value_fn=lambda data: int(data.flameheight + 1),
        set_value_fn=lambda control, value: control.set_flame_height(height=value),
    ),
    IntelliFireNumberEntityDescription(
        key="sleep_control",
        name="Sleep timer",
        icon="mdi:bed-clock",
        mode=NumberMode.AUTO,
        native_max_value=180,
        native_min_value=0,
        native_step=1,
        native_unit_of_measurement="minutes",
        get_value_fn=lambda data: int(data.timeremaining_s / 60),
        set_value_fn=lambda control, value: control.stop_sleep_timer()
        if value == 0
        else control.set_sleep_timer(minutes=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Numbers."""

    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IntelliFireNumber(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_NUMBERS
    )


class IntelliFireNumber(IntellifireEntity, NumberEntity):
    """Define a generic IntelliFire Number Entity."""

    entity_description: IntelliFireNumberEntityDescription

    @property
    def native_value(self) -> int:
        """Return the current Timer value in minutes."""
        return self.entity_description.get_value_fn(self.coordinator.read_api.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set native value."""
        value_to_send = int(value)
        await self.entity_description.set_value_fn(
            self.coordinator.control_api, value_to_send
        )
        await self.coordinator.async_refresh()
