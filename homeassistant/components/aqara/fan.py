"""Support for Aqara Fan."""
from __future__ import annotations

# import json
from typing import Any

from homeassistant.components.fan import FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import AqaraEntity

FANS = {
    "fs",  # Fan
    "kj",  # Air Purifier
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up aqara fan dynamically through aqara discovery."""


class AqaraFanEntity(AqaraEntity, FanEntity):
    """Aqara Fan Device."""

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # self._send_command([{"code": DPCode.MODE, "value": preset_mode}])

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        # self._send_command([{"code": DPCode.FAN_DIRECTION, "value": direction}])

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        # self._send_command([{"code": DPCode.SWITCH, "value": False}])

    def turn_on(
        self,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # self._send_command([{"code": DPCode.SWITCH, "value": True}])

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        # self._send_command([{"code": DPCode.SWITCH_HORIZONTAL, "value": oscillating}])

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        # return self.device.status.get(DPCode.SWITCH, False)

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        # if self.device.status[DPCode.FAN_DIRECTION]:
        #     return DIRECTION_FORWARD
        # return DIRECTION_REVERSE

    @property
    def oscillating(self) -> bool:
        """Return true if the fan is oscillating."""
        # return self.device.status.get(DPCode.SWITCH_HORIZONTAL, False)

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset_modes."""
        # return self.ha_preset_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset_mode."""
        # return self.device.status.get(DPCode.MODE)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        # if not self.is_on:
        #     return 0

        # if (
        #     self.device.category == "kj"
        #     and self.air_purifier_speed_range_len > 1
        #     and not self.air_purifier_speed_range_enum
        #     and DPCode.FAN_SPEED_ENUM in self.device.status
        # ):
        #     # if air-purifier speed enumeration is supported we will prefer it.
        #     return ordered_list_item_to_percentage(
        #         self.air_purifier_speed_range_enum,
        #         self.device.status[DPCode.FAN_SPEED_ENUM],
        #     )

        # # some type may not have the fan_speed_percent key
        # return self.device.status.get(DPCode.FAN_SPEED_PERCENT)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        # if self.device.category == "kj":
        #     return self.air_purifier_speed_range_len
        return super().speed_count

    @property
    def supported_features(self):
        """Flag supported features."""
        # supports = 0
        return
        # if DPCode.MODE in self.device.status:
        #     supports |= SUPPORT_PRESET_MODE
        # if DPCode.FAN_SPEED_PERCENT in self.device.status:
        #     supports |= SUPPORT_SET_SPEED
        # if DPCode.SWITCH_HORIZONTAL in self.device.status:
        #     supports |= SUPPORT_OSCILLATE
        # if DPCode.FAN_DIRECTION in self.device.status:
        #     supports |= SUPPORT_DIRECTION

        # # Air Purifier specific
        # if (
        #     DPCode.SPEED in self.device.status
        #     or DPCode.FAN_SPEED_ENUM in self.device.status
        # ):
        #     supports |= SUPPORT_SET_SPEED
        # return supports
