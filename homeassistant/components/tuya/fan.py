"""Support for Tuya Fan."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
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
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType


def filter_fan_speed_range_list(orginal_list) -> list[str]:
    """Filter 'off' value from fan speeds enum range, because the percentage utility does not expect it."""
    return [speed for speed in orginal_list if speed != "off"]


@dataclass
class TuyaFanEntityDescription(FanEntityDescription):
    """Describe an Tuya fan entity."""

    direction: DPCode | None = None
    oscillate: DPCode | None = None
    presets: DPCode | None = None
    speed: DPCode | None = None
    switch: DPCode | None = None


TUYA_SUPPORT_TYPE = {
    "fs",  # Fan
    "fsd",  # Fan with Light
    "fskg",  # Fan wall switch
    "kj",  # Air Purifier
    "yyj",  # Extractor hood
}

FANS: dict[str, tuple[TuyaFanEntityDescription, ...]] = {
    # Fan
    # https://developer.tuya.com/en/docs/iot/categoryfs?id=Kaiuz1xweel1c
    "fs": (
        TuyaFanEntityDescription(
            key=DPCode.SWITCH,
            direction=DPCode.FAN_DIRECTION,
            # seems to support both horizontal and vertical oscillation
            oscillate=DPCode.SWITCH_HORIZONTAL,
            presets=DPCode.MODE,
            speed=DPCode.FAN_SPEED_PERCENT,
            switch=DPCode.SWITCH,
        ),
    ),
    # Fan with Light
    # https://developer.tuya.com/en/docs/iot/fsd?id=Kaof8eiei4c2v
    "fsd": (
        TuyaFanEntityDescription(
            key=DPCode.FAN_SWITCH,
            direction=DPCode.FAN_DIRECTION,
            presets=DPCode.FAN_MODE,
            speed=DPCode.FAN_SPEED,
            switch=DPCode.FAN_SWITCH,
        ),
    ),
    # Fan wall switch
    # https://developer.tuya.com/en/docs/iot/fskg?id=Kbcs1e383bnra
    "fskg": (
        TuyaFanEntityDescription(
            key=DPCode.SWITCH_FAN,
            speed=DPCode.FAN_SPEED,
            switch=DPCode.SWITCH_FAN,
        ),
    ),
    # Air purifier
    # https://developer.tuya.com/en/docs/iot/categorykj?id=Kaiuz1atqo5l7
    "kj": (
        TuyaFanEntityDescription(
            key=DPCode.SWITCH,
            presets=DPCode.FAN_MODE,
            # Seems to support both 'SPEED' and 'FAN_SPEED_ENUM'
            speed=DPCode.FAN_SPEED_ENUM,
            switch=DPCode.SWITCH,
        ),
    ),
    # Extractor hood
    "yyj": (
        TuyaFanEntityDescription(
            key="",
            speed=DPCode.FAN_SPEED_ENUM,
            switch=None,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya fan dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya fan."""
        entities: list[TuyaFanEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := FANS.get(device.category):
                for description in descriptions:
                    entities.append(
                        TuyaFanEntity(device, hass_data.device_manager, description)
                    )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaFanEntity(TuyaEntity, FanEntity):
    """Tuya Fan Device."""

    entity_description: TuyaFanEntityDescription

    _direction: EnumTypeData | None = None
    _oscillate: DPCode | None = None
    _presets: EnumTypeData | None = None
    _speed: IntegerTypeData | None = None
    _speeds: EnumTypeData | None = None
    _switch: DPCode | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaFanEntityDescription,
    ) -> None:
        """Init Tuya Fan Device."""
        super().__init__(device, device_manager)

        self._switch = self.find_dpcode(description.switch, prefer_function=True)

        self._attr_preset_modes = []
        if enum_type := self.find_dpcode(
            description.presets, dptype=DPType.ENUM, prefer_function=True
        ):
            self._presets = enum_type
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = enum_type.range

        if int_type := self.find_dpcode(
            description.speed, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._speed = int_type
        elif enum_type := self.find_dpcode(
            description.speed, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._speeds = enum_type

        if dpcode := self.find_dpcode(description.oscillate, prefer_function=True):
            self._oscillate = dpcode
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

        if enum_type := self.find_dpcode(
            description.direction, dptype=DPType.ENUM, prefer_function=True
        ):
            self._direction = enum_type
            self._attr_supported_features |= FanEntityFeature.DIRECTION

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if self._presets is None:
            return
        self._send_command([{"code": self._presets.dpcode, "value": preset_mode}])

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if self._direction is None:
            return
        self._send_command([{"code": self._direction.dpcode, "value": direction}])

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self._speed is not None:
            self._send_command(
                [
                    {
                        "code": self._speed.dpcode,
                        "value": int(self._speed.remap_value_from(percentage, 1, 100)),
                    }
                ]
            )
            return

        # Fake turn off
        if self._speeds is not None and percentage == 0 and "off" in self._speeds.range:
            self._send_command(
                [
                    {
                        "code": self._speeds.dpcode,
                        "value": "off",
                    }
                ]
            )
            return

        if self._speeds is not None:
            self._send_command(
                [
                    {
                        "code": self._speeds.dpcode,
                        "value": percentage_to_ordered_list_item(
                            filter_fan_speed_range_list(self._speeds.range),
                            percentage,
                        ),
                    }
                ]
            )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if self._switch is not None:
            self._send_command([{"code": self._switch, "value": False}])

        # Fake turn off
        if (
            self._switch is None
            and self._speeds is not None
            and "off" in self._speeds.range
        ):
            self._send_command(
                [
                    {
                        "code": self._speeds.dpcode,
                        "value": "off",
                    }
                ]
            )

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        commands: list[dict[str, str | bool | int]] = []

        if self._switch is not None:
            commands.append({"code": self._switch, "value": True})

        if percentage is not None and self._speed is not None:
            commands.append(
                {
                    "code": self._speed.dpcode,
                    "value": int(self._speed.remap_value_from(percentage, 1, 100)),
                }
            )

        if percentage is not None and self._speeds is not None:
            commands.append(
                {
                    "code": self._speeds.dpcode,
                    "value": percentage_to_ordered_list_item(
                        filter_fan_speed_range_list(self._speeds.range), percentage
                    ),
                }
            )

        if preset_mode is not None and self._presets is not None:
            commands.append({"code": self._presets.dpcode, "value": preset_mode})

        if (
            self._switch is None
            and percentage is None
            and preset_mode is None
            and self._speeds is not None
        ):
            commands.append(
                {
                    "code": self._speeds.dpcode,
                    "value": filter_fan_speed_range_list(self._speeds.range)[0],
                }
            )

        self._send_command(commands)

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        if self._oscillate is None:
            return
        self._send_command([{"code": self._oscillate, "value": oscillating}])

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""

        if self._switch is not None:
            return self.device.status.get(self._switch)

        # Fake on/off reporting
        if (
            self._switch is None
            and self._speeds is not None
            and "off" in self._speeds.range
        ):
            return self.device.status.get(self._speeds.dpcode) != "off"

        return None

    @property
    def current_direction(self) -> str | None:
        """Return the current direction of the fan."""
        if (
            self._direction is None
            or (value := self.device.status.get(self._direction.dpcode)) is None
        ):
            return None

        if value.lower() == DIRECTION_FORWARD:
            return DIRECTION_FORWARD

        if value.lower() == DIRECTION_REVERSE:
            return DIRECTION_REVERSE

        return None

    @property
    def oscillating(self) -> bool | None:
        """Return true if the fan is oscillating."""
        if self._oscillate is None:
            return None
        return self.device.status.get(self._oscillate)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset_mode."""
        if self._presets is None:
            return None
        return self.device.status.get(self._presets.dpcode)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        if self._speed is not None:
            if (value := self.device.status.get(self._speed.dpcode)) is None:
                return None
            return int(self._speed.remap_value_to(value, 1, 100))

        if self._speeds is not None:
            if (value := self.device.status.get(self._speeds.dpcode)) is None:
                return None
            if (value := self.device.status.get(self._speeds.dpcode)) == "off":
                return 0
            return ordered_list_item_to_percentage(
                filter_fan_speed_range_list(self._speeds.range), value
            )

        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self._speeds is not None:
            return len(filter_fan_speed_range_list(self._speeds.range))
        return 100
