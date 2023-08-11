"""Define switch func."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from intellifire4py import IntellifirePollData
from intellifire4py.intellifire import IntellifireAPILocal

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass()
class IntellifireSwitchRequiredKeysMixin:
    """Mixin for required keys."""

    on_fn: Callable[[IntellifireAPILocal], Awaitable]
    off_fn: Callable[[IntellifireAPILocal], Awaitable]
    value_fn: Callable[[IntellifirePollData], bool]


@dataclass
class IntellifireSwitchEntityDescription(
    SwitchEntityDescription, IntellifireSwitchRequiredKeysMixin
):
    """Describes a switch entity."""


INTELLIFIRE_SWITCHES: tuple[IntellifireSwitchEntityDescription, ...] = (
    IntellifireSwitchEntityDescription(
        key="on_off",
        translation_key="flame",
        on_fn=lambda control_api: control_api.flame_on(),
        off_fn=lambda control_api: control_api.flame_off(),
        value_fn=lambda data: data.is_on,
    ),
    IntellifireSwitchEntityDescription(
        key="pilot",
        translation_key="pilot_light",
        icon="mdi:fire-alert",
        on_fn=lambda control_api: control_api.pilot_on(),
        off_fn=lambda control_api: control_api.pilot_off(),
        value_fn=lambda data: data.pilot_on,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure switch entities."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IntellifireSwitch(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_SWITCHES
    )


class IntellifireSwitch(IntellifireEntity, SwitchEntity):
    """Define an Intellifire Switch."""

    entity_description: IntellifireSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.on_fn(self.coordinator.control_api)
        await self.async_update_ha_state(force_refresh=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.off_fn(self.coordinator.control_api)
        await self.async_update_ha_state(force_refresh=True)

    @property
    def is_on(self) -> bool | None:
        """Return the on state."""
        return self.entity_description.value_fn(self.coordinator.read_api.data)
