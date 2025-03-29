"""Support for lights through the SmartThings cloud API."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from pysmartthings import Attribute, Capability, Command, DeviceEvent, SmartThings

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

CAPABILITIES = (
    Capability.SWITCH_LEVEL,
    Capability.COLOR_CONTROL,
    Capability.COLOR_TEMPERATURE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsLight(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.SWITCH in device.status[MAIN]
        and any(capability in device.status[MAIN] for capability in CAPABILITIES)
    )


def convert_scale(
    value: float, value_scale: int, target_scale: int, round_digits: int = 4
) -> float:
    """Convert a value to a different scale."""
    return round(value * target_scale / value_scale, round_digits)


class SmartThingsLight(SmartThingsEntity, LightEntity, RestoreEntity):
    """Define a SmartThings Light."""

    _attr_name = None
    _attr_supported_color_modes: set[ColorMode]

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler. This value is the
    # lowest kelvin found supported across 20+ handlers.
    _attr_min_color_temp_kelvin = 2000  # 500 mireds

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler. This value is the
    # highest kelvin found supported across 20+ handlers.
    _attr_max_color_temp_kelvin = 9000  # 111 mireds

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize a SmartThingsLight."""
        super().__init__(
            client,
            device,
            {
                Capability.COLOR_CONTROL,
                Capability.COLOR_TEMPERATURE,
                Capability.SWITCH_LEVEL,
                Capability.SWITCH,
            },
        )
        color_modes = set()
        if self.supports_capability(Capability.COLOR_TEMPERATURE):
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if self.supports_capability(Capability.COLOR_CONTROL):
            color_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS
        if not color_modes and self.supports_capability(Capability.SWITCH_LEVEL):
            color_modes.add(ColorMode.BRIGHTNESS)
        if not color_modes:
            color_modes.add(ColorMode.ONOFF)
        if len(color_modes) == 1:
            self._attr_color_mode = list(color_modes)[0]
        self._attr_supported_color_modes = color_modes
        features = LightEntityFeature(0)
        if self.supports_capability(Capability.SWITCH_LEVEL):
            features |= LightEntityFeature.TRANSITION
        self._attr_supported_features = features

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_extra_data()) is not None:
            self._attr_color_mode = last_state.as_dict()[ATTR_COLOR_MODE]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        tasks = []
        # Color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            tasks.append(self.async_set_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN]))
        # Color
        if ATTR_HS_COLOR in kwargs:
            tasks.append(self.async_set_color(kwargs[ATTR_HS_COLOR]))
        if tasks:
            # Set temp/color first
            await asyncio.gather(*tasks)

        # Switch/brightness/transition
        if ATTR_BRIGHTNESS in kwargs:
            await self.async_set_level(
                kwargs[ATTR_BRIGHTNESS], kwargs.get(ATTR_TRANSITION, 0)
            )
        else:
            await self.execute_device_command(
                Capability.SWITCH,
                Command.ON,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Switch/transition
        if ATTR_TRANSITION in kwargs:
            await self.async_set_level(0, int(kwargs[ATTR_TRANSITION]))
        else:
            await self.execute_device_command(
                Capability.SWITCH,
                Command.OFF,
            )

    def _update_attr(self) -> None:
        """Update entity attributes when the device status has changed."""
        # Brightness and transition
        if brightness_supported(self._attr_supported_color_modes):
            if (
                brightness := self.get_attribute_value(
                    Capability.SWITCH_LEVEL, Attribute.LEVEL
                )
            ) is None:
                self._attr_brightness = None
            else:
                self._attr_brightness = int(
                    convert_scale(
                        brightness,
                        100,
                        255,
                        0,
                    )
                )
        # Color Temperature
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp_kelvin = self.get_attribute_value(
                Capability.COLOR_TEMPERATURE, Attribute.COLOR_TEMPERATURE
            )
        # Color
        if ColorMode.HS in self._attr_supported_color_modes:
            if (
                hue := self.get_attribute_value(Capability.COLOR_CONTROL, Attribute.HUE)
            ) is None:
                self._attr_hs_color = None
            else:
                self._attr_hs_color = (
                    convert_scale(
                        hue,
                        100,
                        360,
                    ),
                    self.get_attribute_value(
                        Capability.COLOR_CONTROL, Attribute.SATURATION
                    ),
                )

    async def async_set_color(self, hs_color):
        """Set the color of the device."""
        hue = convert_scale(float(hs_color[0]), 360, 100)
        hue = max(min(hue, 100.0), 0.0)
        saturation = max(min(float(hs_color[1]), 100.0), 0.0)
        await self.execute_device_command(
            Capability.COLOR_CONTROL,
            Command.SET_COLOR,
            argument={"hue": hue, "saturation": saturation},
        )

    async def async_set_color_temp(self, value: int):
        """Set the color temperature of the device."""
        kelvin = max(min(value, 30000), 1)
        await self.execute_device_command(
            Capability.COLOR_TEMPERATURE,
            Command.SET_COLOR_TEMPERATURE,
            argument=kelvin,
        )

    async def async_set_level(self, brightness: int, transition: int) -> None:
        """Set the brightness of the light over transition."""
        level = int(convert_scale(brightness, 255, 100, 0))
        # Due to rounding, set level to 1 (one) so we don't inadvertently
        # turn off the light when a low brightness is set.
        level = 1 if level == 0 and brightness > 0 else level
        level = max(min(level, 100), 0)
        duration = int(transition)
        await self.execute_device_command(
            Capability.SWITCH_LEVEL,
            Command.SET_LEVEL,
            argument=[level, duration],
        )

    def _update_handler(self, event: DeviceEvent) -> None:
        """Handle device updates."""
        if event.capability in (Capability.COLOR_CONTROL, Capability.COLOR_TEMPERATURE):
            self._attr_color_mode = {
                Capability.COLOR_CONTROL: ColorMode.HS,
                Capability.COLOR_TEMPERATURE: ColorMode.COLOR_TEMP,
            }[cast(Capability, event.capability)]
        super()._update_handler(event)

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        if (
            state := self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH)
        ) is None:
            return None
        return state == "on"
