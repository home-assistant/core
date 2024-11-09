"""Representation of a fan."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ZWaveMePlatform
from .entity import ZWaveMeEntity

DEVICE_NAME = ZWaveMePlatform.FAN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan platform."""

    @callback
    def add_new_device(new_device):
        controller = hass.data[DOMAIN][config_entry.entry_id]
        fan = ZWaveMeFan(controller, new_device)

        async_add_entities(
            [
                fan,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeFan(ZWaveMeEntity, FanEntity):
    """Representation of a ZWaveMe Fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        if self.device.level == 99:  # Scale max value
            return 100
        return self.device.level

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        self.controller.zwave_api.send_command(
            self.device.id, f"exact?level={min(percentage, 99)}"
        )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self.controller.zwave_api.send_command(self.device.id, "exact?level=0")

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        self.set_percentage(percentage if percentage is not None else 99)
