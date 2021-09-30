"""Support for Tuya Fan."""
from __future__ import annotations

import json
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as DEVICE_DOMAIN,
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

from .base import TuyaHaEntity
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)


# Fan
# https://developer.tuya.com/en/docs/iot/f?id=K9gf45vs7vkge
DPCODE_SWITCH = "switch"
DPCODE_FAN_SPEED = "fan_speed_percent"
DPCODE_MODE = "mode"
DPCODE_SWITCH_HORIZONTAL = "switch_horizontal"
DPCODE_FAN_DIRECTION = "fan_direction"

# Air Purifier
# https://developer.tuya.com/en/docs/iot/s?id=K9gf48r41mn81
DPCODE_AP_FAN_SPEED = "speed"
DPCODE_AP_FAN_SPEED_ENUM = "fan_speed_enum"

TUYA_SUPPORT_TYPE = {
    "fs",  # Fan
    "kj",  # Air Purifier
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up tuya fan dynamically through tuya discovery."""
    _LOGGER.debug("fan init")

    hass.data[DOMAIN][entry.entry_id][TUYA_HA_TUYA_MAP][
        DEVICE_DOMAIN
    ] = TUYA_SUPPORT_TYPE

    @callback
    def async_discover_device(dev_ids: list[str]) -> None:
        """Discover and add a discovered tuya fan."""
        _LOGGER.debug("fan add-> %s", dev_ids)
        if not dev_ids:
            return
        entities = _setup_entities(hass, entry, dev_ids)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
        )
    )

    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.device_map.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    async_discover_device(device_ids)


def _setup_entities(
    hass: HomeAssistant, entry: ConfigEntry, device_ids: list[str]
) -> list[TuyaHaFan]:
    """Set up Tuya Fan."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue
        entities.append(TuyaHaFan(device, device_manager))
        hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(device_id)
    return entities


class TuyaHaFan(TuyaHaEntity, FanEntity):
    """Tuya Fan Device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init Tuya Fan Device."""
        super().__init__(device, device_manager)

        self.ha_preset_modes = []
        if DPCODE_MODE in self.tuya_device.function:
            self.ha_preset_modes = json.loads(
                self.tuya_device.function[DPCODE_MODE].values
            ).get("range", [])

        # Air purifier fan can be controlled either via the ranged values or via the enum.
        # We will always prefer the enumeration if available
        #   Enum is used for e.g. MEES SmartHIMOX-H06
        #   Range is used for e.g. Concept CA3000
        self.air_purifier_speed_range_len = 0
        self.air_purifier_speed_range_enum = []
        if self.tuya_device.category == "kj" and (
            DPCODE_AP_FAN_SPEED_ENUM in self.tuya_device.function
            or DPCODE_AP_FAN_SPEED in self.tuya_device.function
        ):
            if DPCODE_AP_FAN_SPEED_ENUM in self.tuya_device.function:
                self.dp_code_speed_enum = DPCODE_AP_FAN_SPEED_ENUM
            else:
                self.dp_code_speed_enum = DPCODE_AP_FAN_SPEED

            data = json.loads(
                self.tuya_device.function[self.dp_code_speed_enum].values
            ).get("range")
            if data:
                self.air_purifier_speed_range_len = len(data)
                self.air_purifier_speed_range_enum = data

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        self._send_command([{"code": DPCODE_MODE, "value": preset_mode}])

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._send_command([{"code": DPCODE_FAN_DIRECTION, "value": direction}])

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self.tuya_device.category == "kj":
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
            self._send_command([{"code": DPCODE_FAN_SPEED, "value": percentage}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._send_command([{"code": DPCODE_SWITCH, "value": False}])

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        self._send_command([{"code": DPCODE_SWITCH, "value": True}])

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        self._send_command([{"code": DPCODE_SWITCH_HORIZONTAL, "value": oscillating}])

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.tuya_device.status.get(DPCODE_SWITCH, False)

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if self.tuya_device.status[DPCODE_FAN_DIRECTION]:
            return DIRECTION_FORWARD
        return DIRECTION_REVERSE

    @property
    def oscillating(self) -> bool:
        """Return true if the fan is oscillating."""
        return self.tuya_device.status.get(DPCODE_SWITCH_HORIZONTAL, False)

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset_modes."""
        return self.ha_preset_modes

    @property
    def preset_mode(self) -> str:
        """Return the current preset_mode."""
        return self.tuya_device.status[DPCODE_MODE]

    @property
    def percentage(self) -> int:
        """Return the current speed."""
        if not self.is_on:
            return 0

        if (
            self.tuya_device.category == "kj"
            and self.air_purifier_speed_range_len > 1
            and not self.air_purifier_speed_range_enum
            and DPCODE_AP_FAN_SPEED_ENUM in self.tuya_device.status
        ):
            # if air-purifier speed enumeration is supported we will prefer it.
            return ordered_list_item_to_percentage(
                self.air_purifier_speed_range_enum,
                self.tuya_device.status[DPCODE_AP_FAN_SPEED_ENUM],
            )

        return self.tuya_device.status[DPCODE_FAN_SPEED]

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self.tuya_device.category == "kj":
            return self.air_purifier_speed_range_len
        return super().speed_count

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = 0
        if DPCODE_MODE in self.tuya_device.status:
            supports |= SUPPORT_PRESET_MODE
        if DPCODE_FAN_SPEED in self.tuya_device.status:
            supports |= SUPPORT_SET_SPEED
        if DPCODE_SWITCH_HORIZONTAL in self.tuya_device.status:
            supports |= SUPPORT_OSCILLATE
        if DPCODE_FAN_DIRECTION in self.tuya_device.status:
            supports |= SUPPORT_DIRECTION

        # Air Purifier specific
        if (
            DPCODE_AP_FAN_SPEED in self.tuya_device.status
            or DPCODE_AP_FAN_SPEED_ENUM in self.tuya_device.status
        ):
            supports |= SUPPORT_SET_SPEED
        return supports
