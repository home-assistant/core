"""Support for Tuya Fan."""
from __future__ import annotations

import json
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

TUYA_SUPPORT_TYPE = {
    "fs",  # Fan
    "kj",  # Air Purifier
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up tuya fan dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya fan."""
        entities: list[TuyaFanEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in TUYA_SUPPORT_TYPE:
                entities.append(TuyaFanEntity(device, hass_data.device_manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaFanEntity(TuyaEntity, FanEntity):
    """Tuya Fan Device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init Tuya Fan Device."""
        super().__init__(device, device_manager)

        self.ha_preset_modes = []
        if DPCode.MODE in self.device.function:
            self.ha_preset_modes = json.loads(
                self.device.function[DPCode.MODE].values
            ).get("range", [])

        # Air purifier fan can be controlled either via the ranged values or via the enum.
        # We will always prefer the enumeration if available
        #   Enum is used for e.g. MEES SmartHIMOX-H06
        #   Range is used for e.g. Concept CA3000
        self.air_purifier_speed_range_len = 0
        self.air_purifier_speed_range_enum = []
        if self.device.category == "kj" and (
            DPCode.FAN_SPEED_ENUM in self.device.function
            or DPCode.SPEED in self.device.function
        ):
            if DPCode.FAN_SPEED_ENUM in self.device.function:
                self.dp_code_speed_enum = DPCode.FAN_SPEED_ENUM
            else:
                self.dp_code_speed_enum = DPCode.SPEED

            data = json.loads(self.device.function[self.dp_code_speed_enum].values).get(
                "range"
            )
            if data:
                self.air_purifier_speed_range_len = len(data)
                self.air_purifier_speed_range_enum = data

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        self._send_command([{"code": DPCode.MODE, "value": preset_mode}])

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._send_command([{"code": DPCode.FAN_DIRECTION, "value": direction}])

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self.device.category == "kj":
            value_in_range = percentage_to_ordered_list_item(
                self.air_purifier_speed_range_enum, percentage
            )
            self._send_command(
                [
                    {
                        "code": self.dp_code_speed_enum,
                        "value": value_in_range,
                    }
                ]
            )
        else:
            self._send_command(
                [{"code": DPCode.FAN_SPEED_PERCENT, "value": percentage}]
            )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._send_command([{"code": DPCode.SWITCH, "value": False}])

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        self._send_command([{"code": DPCode.SWITCH, "value": True}])

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        self._send_command([{"code": DPCode.SWITCH_HORIZONTAL, "value": oscillating}])

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.device.status.get(DPCode.SWITCH, False)

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if self.device.status[DPCode.FAN_DIRECTION]:
            return DIRECTION_FORWARD
        return DIRECTION_REVERSE

    @property
    def oscillating(self) -> bool:
        """Return true if the fan is oscillating."""
        return self.device.status.get(DPCode.SWITCH_HORIZONTAL, False)

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset_modes."""
        return self.ha_preset_modes

    @property
    def preset_mode(self) -> str:
        """Return the current preset_mode."""
        return self.device.status[DPCode.MODE]

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        if not self.is_on:
            return 0

        if (
            self.device.category == "kj"
            and self.air_purifier_speed_range_len > 1
            and not self.air_purifier_speed_range_enum
            and DPCode.FAN_SPEED_ENUM in self.device.status
        ):
            # if air-purifier speed enumeration is supported we will prefer it.
            return ordered_list_item_to_percentage(
                self.air_purifier_speed_range_enum,
                self.device.status[DPCode.FAN_SPEED_ENUM],
            )

        # some type may not have the fan_speed_percent key
        return self.device.status.get(DPCode.FAN_SPEED_PERCENT)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self.device.category == "kj":
            return self.air_purifier_speed_range_len
        return super().speed_count

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = 0
        if DPCode.MODE in self.device.status:
            supports |= SUPPORT_PRESET_MODE
        if DPCode.FAN_SPEED_PERCENT in self.device.status:
            supports |= SUPPORT_SET_SPEED
        if DPCode.SWITCH_HORIZONTAL in self.device.status:
            supports |= SUPPORT_OSCILLATE
        if DPCode.FAN_DIRECTION in self.device.status:
            supports |= SUPPORT_DIRECTION

        # Air Purifier specific
        if (
            DPCode.SPEED in self.device.status
            or DPCode.FAN_SPEED_ENUM in self.device.status
        ):
            supports |= SUPPORT_SET_SPEED
        return supports
