"""Switch platform for NRGkick."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import async_api_call
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NRGkickSwitchEntityDescription(SwitchEntityDescription):
    """Class describing NRGkick switch entities."""

    is_on_fn: Callable[[NRGkickData], bool]
    set_is_on_fn: Callable[[NRGkickDataUpdateCoordinator, bool], Awaitable[None]]


def _is_charging_enabled(data: NRGkickData) -> bool:
    """Return True if charging is enabled (not paused)."""
    charge_pause = data.control.get("charge_pause")
    return charge_pause == 0


async def _async_set_charging_enabled(
    coordinator: NRGkickDataUpdateCoordinator, is_on: bool
) -> None:
    """Enable or pause charging.

    The NRGkick API uses a pause flag (pause=True means charging is paused).
    """
    await async_api_call(coordinator.api.set_charge_pause(not is_on))
    await coordinator.async_refresh()


SWITCHES: tuple[NRGkickSwitchEntityDescription, ...] = (
    NRGkickSwitchEntityDescription(
        key="charging_enabled",
        translation_key="charging_enabled",
        is_on_fn=_is_charging_enabled,
        set_is_on_fn=_async_set_charging_enabled,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick switches based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        NRGkickSwitch(coordinator, description) for description in SWITCHES
    )


class NRGkickSwitch(NRGkickEntity, SwitchEntity):
    """Representation of a NRGkick switch."""

    entity_description: NRGkickSwitchEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        entity_description: NRGkickSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        data = self.coordinator.data
        assert data is not None
        return self.entity_description.is_on_fn(data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on (enable charging)."""
        await self.entity_description.set_is_on_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off (pause charging)."""
        await self.entity_description.set_is_on_fn(self.coordinator, False)
