"""Switch entities for Trinnov Altitude integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class TrinnovAltitudeSwitchEntityDescription(SwitchEntityDescription):
    """Describes Trinnov Altitude switch entity."""

    value_fn: Callable[[Any], bool]
    turn_on_fn: Callable[[Any], Awaitable[None]]
    turn_off_fn: Callable[[Any], Awaitable[None]]


SWITCHES: tuple[TrinnovAltitudeSwitchEntityDescription, ...] = (
    TrinnovAltitudeSwitchEntityDescription(
        key="mute",
        translation_key="mute",
        name="Mute",
        value_fn=lambda state: bool(state.mute),
        turn_on_fn=lambda device: device.mute_set(True),
        turn_off_fn=lambda device: device.mute_set(False),
    ),
    TrinnovAltitudeSwitchEntityDescription(
        key="dim",
        translation_key="dim",
        name="Dim",
        value_fn=lambda state: bool(state.dim),
        turn_on_fn=lambda device: device.dim_set(True),
        turn_off_fn=lambda device: device.dim_set(False),
    ),
    TrinnovAltitudeSwitchEntityDescription(
        key="bypass",
        translation_key="bypass",
        name="Bypass",
        value_fn=lambda state: bool(state.bypass),
        turn_on_fn=lambda device: device.bypass_set(True),
        turn_off_fn=lambda device: device.bypass_set(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities from config entry."""
    async_add_entities(
        [
            TrinnovAltitudeSwitch(entry.runtime_data, description)
            for description in SWITCHES
        ]
    )


class TrinnovAltitudeSwitch(TrinnovAltitudeEntity, SwitchEntity):
    """Representation of a Trinnov Altitude switch."""

    entity_description: TrinnovAltitudeSwitchEntityDescription

    def __init__(
        self, device, entity_description: TrinnovAltitudeSwitchEntityDescription
    ) -> None:
        """Initialize switch."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self._device.state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.entity_description.turn_on_fn(self._device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.entity_description.turn_off_fn(self._device)
