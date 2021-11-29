"""Support for Xiaomi WalkingPad treadmill remote."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WalkingPadEntity
from .const import DOMAIN

PARALLEL_UPDATES: Final = 1
SCAN_INTERVAL: Final = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WalkingPad from a config entry."""
    device = hass.data[DOMAIN][config_entry.entry_id]

    entities = [WalkingPadRemote(device)]
    async_add_entities(entities)


class WalkingPadRemote(WalkingPadEntity, RemoteEntity):
    """WalkingPad Remote."""

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{self.device.config.entry_id}-remote"

    @property
    def name(self) -> str:
        """Return the name of the remote."""
        return f"{self.device.name}-remote"

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        if self.device.state == STATE_ON:
            return True
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device specific state attributes."""
        if self.available:
            attributes = {
                "mode": self.device.mode,
                "steps": self.device.steps,
                "speed": self.device.speed,
                "time": self.device.time,
                "dist": self.device.dist,
                "max_speed": self.device.max_speed,
                "min_speed": self.device.min_speed,
                "speed_user": self.device.speed_user,
                "default_speed": self.device.default_speed,
            }
            return attributes
        else:
            return None

    async def set_speed_user(self, speed: float) -> None:
        """Set user speed."""
        await self.device.set_speed_user(speed)

    async def set_speed(self, speed: float) -> None:
        """Set current speed."""
        await self.device.set_speed(speed)

    async def set_mode(self, mode: str) -> None:
        """Set device mode."""
        await self.device.set_mode(mode)

    async def start_belt(self) -> None:
        """Start belt."""
        await self.device.start_belt()

    async def stop_belt(self) -> None:
        """Stop belt."""
        await self.device.stop_belt()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on device."""
        await self.set_mode("manual")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off device."""
        await self.set_mode("standby")

    async def async_update(self) -> None:
        """Update the entity."""
        await self.device.async_update()
