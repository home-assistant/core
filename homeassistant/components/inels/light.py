"""iNELS light."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from inelsmqtt.devices import Device

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    filter_supported_color_modes,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InelsConfigEntry
from .entity import InelsBaseEntity


@dataclass(frozen=True, kw_only=True)
class InelsLightEntityDescription(LightEntityDescription):
    """Class describing iNELS light entities."""

    get_state_fn: Callable[[Device, int], Any]
    get_last_state_fn: Callable[[Device, int], Any]
    color_modes: list[ColorMode]
    alerts: list[str] | None = None
    placeholder_fn: Callable[[Device, int, bool], dict[str, str]]


LIGHT_TYPES = [
    InelsLightEntityDescription(
        key="simple_light",
        translation_key="simple_light",
        get_state_fn=lambda device, index: device.state.simple_light[index],
        get_last_state_fn=lambda device, index: (
            device.last_values.ha_value.simple_light[index]
        ),
        color_modes=[ColorMode.BRIGHTNESS],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="light_coa_toa",
        translation_key="light_coa_toa",
        get_state_fn=lambda device, index: device.state.light_coa_toa[index],
        get_last_state_fn=lambda device, index: (
            device.last_values.ha_value.light_coa_toa[index]
        ),
        color_modes=[ColorMode.BRIGHTNESS],
        alerts=["coa", "toa"],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="dali",
        translation_key="dali",
        get_state_fn=lambda device, index: device.state.dali[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.dali[index],
        color_modes=[ColorMode.BRIGHTNESS],
        alerts=["alert_dali_communication", "alert_dali_power"],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="aout",
        translation_key="aout",
        icon="mdi:flash",
        get_state_fn=lambda device, index: device.state.aout[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.aout[index],
        color_modes=[ColorMode.BRIGHTNESS],
        alerts=["aout_coa"],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="rgb",
        translation_key="rgb",
        get_state_fn=lambda device, index: device.state.rgb[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.rgb[index],
        color_modes=[ColorMode.RGB],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="rgbw",
        translation_key="rgbw",
        get_state_fn=lambda device, index: device.state.rgbw[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.rgbw[index],
        color_modes=[ColorMode.RGBW],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsLightEntityDescription(
        key="warm_light",
        translation_key="warm_light",
        get_state_fn=lambda device, index: device.state.warm_light[index],
        get_last_state_fn=lambda device, index: (
            device.last_values.ha_value.warm_light[index]
        ),
        color_modes=[ColorMode.COLOR_TEMP],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load iNELS lights."""
    entities: list[InelsLight] = []

    for device in entry.runtime_data.devices:
        for description in LIGHT_TYPES:
            if hasattr(device.state, description.key):
                light_count = len(getattr(device.state, description.key))

                entities.extend(
                    InelsLight(
                        device=device,
                        description=description,
                        index=idx,
                        light_count=light_count,
                    )
                    for idx in range(light_count)
                )

    async_add_entities(entities, False)


class InelsLight(InelsBaseEntity, LightEntity):
    """Light class for HA."""

    entity_description: InelsLightEntityDescription

    def __init__(
        self,
        device: Device,
        description: InelsLightEntityDescription,
        index: int = 0,
        light_count: int = 1,
    ) -> None:
        """Initialize a light."""
        super().__init__(device=device, key=description.key, index=index)
        self.entity_description = description
        self._light_count = light_count

        # Include index in unique_id for devices with multiple lights
        unique_key = (
            f"{description.key}{index}" if self._light_count > 1 else description.key
        )

        self._attr_unique_id = f"{self._attr_unique_id}_{unique_key}".lower()

        # Set translation placeholders
        self._attr_translation_placeholders = self.entity_description.placeholder_fn(
            self._device, self._index, self._light_count > 1
        )

        # Set supported color modes
        self._attr_supported_color_modes = filter_supported_color_modes(
            description.color_modes
        )
        self._attr_min_color_temp_kelvin = 2700  # standard color temp
        self._attr_max_color_temp_kelvin = 6500  # standard color temp

    def _check_alerts(self, current_state: Any) -> None:
        """Check if there are active alerts and raise ServiceValidationError if found."""
        if self.entity_description.alerts and any(
            getattr(current_state, alert_key, None)
            for alert_key in self.entity_description.alerts
        ):
            raise ServiceValidationError("Cannot operate light with active alerts")

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        return bool(current_state.brightness > 0)

    @property
    def brightness(self) -> int | None:
        """Light brightness."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        return int(round(current_state.brightness * 2.55))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        if hasattr(current_state, "r"):
            return (current_state.r, current_state.g, current_state.b)
        return None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color value."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        if hasattr(current_state, "w"):
            return (
                round(current_state.r * 2.55),
                round(current_state.g * 2.55),
                round(current_state.b * 2.55),
                round(current_state.w * 2.55),
            )
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        if hasattr(current_state, "relative_ct"):
            return int(
                (current_state.relative_ct / 100)
                * (self.max_color_temp_kelvin - self.min_color_temp_kelvin)
                + self.min_color_temp_kelvin
            )
        return None

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        if hasattr(current_state, "w"):
            return ColorMode.RGBW
        if hasattr(current_state, "r"):
            return ColorMode.RGB
        if hasattr(current_state, "relative_ct"):
            return ColorMode.COLOR_TEMP

        return ColorMode.BRIGHTNESS

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Light to turn off."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        self._check_alerts(current_state)

        # Store brightness before turning off
        current_state.brightness_before_off = current_state.brightness
        current_state.brightness = 0

        await self._device.set_ha_value(self._device.state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Light to turn on."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        self._check_alerts(current_state)

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            current_state.r = rgb[0]
            current_state.g = rgb[1]
            current_state.b = rgb[2]
        elif ATTR_RGBW_COLOR in kwargs:
            rgbw = kwargs[ATTR_RGBW_COLOR]
            current_state.r = int(rgbw[0] / 2.55)
            current_state.g = int(rgbw[1] / 2.55)
            current_state.b = int(rgbw[2] / 2.55)
            current_state.w = int(rgbw[3] / 2.55)
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 2.55)
            brightness = min(brightness, 100)
            current_state.brightness = brightness
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp = int(kwargs[ATTR_COLOR_TEMP_KELVIN])
            current_state.relative_ct = int(  # 0-100%
                100
                * (color_temp - self.min_color_temp_kelvin)
                / (self.max_color_temp_kelvin - self.min_color_temp_kelvin)
            )
        else:
            try:
                last_state = self.entity_description.get_last_state_fn(
                    self._device, self._index
                )
            except (AttributeError, IndexError):
                last_state = None

            if self._key == "light_coa_toa":
                # Since ramp increments are built into events,
                # the last value is never identical to the value before off
                current_state.brightness = (
                    100
                    if last_state is None
                    or last_state.brightness_before_off in [0, None]
                    else last_state.brightness_before_off
                )
            else:
                # Turn on to previous brightness or 100%
                current_state.brightness = (
                    100
                    if last_state is None or last_state.brightness == 0
                    else last_state.brightness
                )

        await self._device.set_ha_value(self._device.state)
