"""Switch support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Valve

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MelnorDataUpdateCoordinator
from .entity import MelnorZoneEntity, get_entities_for_valves


@dataclass(frozen=True, kw_only=True)
class MelnorSwitchEntityDescription(SwitchEntityDescription):
    """Describes Melnor switch entity."""

    on_off_fn: Callable[[Valve, bool], Coroutine[Any, Any, None]]
    state_fn: Callable[[Valve], Any]


ZONE_ENTITY_DESCRIPTIONS = [
    MelnorSwitchEntityDescription(
        device_class=SwitchDeviceClass.SWITCH,
        key="manual",
        translation_key="manual",
        name=None,
        on_off_fn=lambda valve, bool: valve.set_is_watering(bool),
        state_fn=lambda valve: valve.is_watering,
    ),
    MelnorSwitchEntityDescription(
        device_class=SwitchDeviceClass.SWITCH,
        key="frequency",
        translation_key="frequency",
        on_off_fn=lambda valve, bool: valve.set_frequency_enabled(bool),
        state_fn=lambda valve: valve.schedule_enabled,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        get_entities_for_valves(
            coordinator,
            ZONE_ENTITY_DESCRIPTIONS,
            lambda valve, description: MelnorZoneSwitch(
                coordinator, description, valve
            ),
        )
    )


class MelnorZoneSwitch(MelnorZoneEntity, SwitchEntity):
    """A switch implementation for a melnor device."""

    entity_description: MelnorSwitchEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorSwitchEntityDescription,
        valve: Valve,
    ) -> None:
        """Initialize a switch for a melnor device."""
        super().__init__(coordinator, entity_description, valve)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.state_fn(self._valve)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.entity_description.on_off_fn(self._valve, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.entity_description.on_off_fn(self._valve, False)
        self.async_write_ha_state()
