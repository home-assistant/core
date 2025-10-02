"""OpenRGB light platform."""

from __future__ import annotations

from typing import Any

from openrgb.orgb import Device
from openrgb.utils import DeviceType, ModeData, ModeFlags, OpenRGBDisconnected, RGBColor

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import color_hs_to_RGB, color_RGB_to_hsv

from .const import (
    DEFAULT_BRIGHTNESS,
    DEFAULT_COLOR,
    DOMAIN,
    EFFECT_OFF_OPENRGB_MODES,
    OFF_COLOR,
    OPENRGB_MODE_DIRECT,
    OPENRGB_MODE_OFF,
    OPENRGB_MODE_STATIC,
)
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRGBConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenRGB light platform."""
    coordinator = config_entry.runtime_data
    known_device_keys: set[str] = set()

    def _check_device() -> None:
        """Add entities for newly discovered OpenRGB devices."""
        current_keys: set[str] = set(coordinator.data.keys())
        new_keys: set[str] = current_keys - known_device_keys
        if new_keys:
            known_device_keys.update(new_keys)
            async_add_entities(
                [OpenRGBLight(coordinator, device_key) for device_key in new_keys]
            )

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


class OpenRGBLight(CoordinatorEntity[OpenRGBCoordinator], LightEntity):
    """Representation of an OpenRGB light."""

    _attr_has_entity_name = True
    _attr_name = None  # Use the device name
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT

    _mode: str | None = None

    _supports_color_modes: list[str]
    _preferred_no_effect_mode: str
    _supports_off_mode: bool

    _previous_brightness: int | None = None
    _previous_rgb_color: tuple[int, int, int] | None = None
    _previous_mode: str | None = None

    def __init__(self, coordinator: OpenRGBCoordinator, device_key: str) -> None:
        """Initialize the OpenRGB light."""
        super().__init__(coordinator)
        self.device_key = device_key
        self._attr_unique_id = device_key

        device_name = coordinator.get_device_name(device_key)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=device_name,
            manufacturer=self.device.metadata.vendor,
            model=self.device.metadata.description,
            model_id=self.device.type.name,
            sw_version=self.device.metadata.version,
            serial_number=self.device.metadata.serial,
            via_device=(DOMAIN, coordinator.entry_id),
        )

        modes = [mode.name for mode in self.device.modes]
        # Prefer Static mode over Direct
        self._preferred_no_effect_mode = (
            OPENRGB_MODE_STATIC if OPENRGB_MODE_STATIC in modes else OPENRGB_MODE_DIRECT
        )
        # Determine if the device supports being turned off through modes
        self._supports_off_mode = OPENRGB_MODE_OFF in modes
        # Determine which modes supports color
        self._supports_color_modes = [
            mode.name
            for mode in self.device.modes
            if check_if_mode_supports_color(mode)
        ]
        # Convert modes to effects by excluding Off and effect-off modes
        self._attr_effect_list = [EFFECT_OFF] + [
            mode
            for mode in modes
            if mode != OPENRGB_MODE_OFF and mode not in EFFECT_OFF_OPENRGB_MODES
        ]

        icon = get_icon(self.device.type)
        if icon is not None:
            self._attr_icon = f"mdi:{icon}"

        self._update_attrs()

    @callback
    def _update_attrs(self) -> None:
        """Update the attributes based on the current device state."""
        mode_data = self.device.modes[self.device.active_mode]
        mode = mode_data.name
        if mode == OPENRGB_MODE_OFF:
            mode = None
            mode_supports_colors = False
        else:
            mode_supports_colors = check_if_mode_supports_color(mode_data)

        rgb_color = None
        brightness = None
        on_by_color = True
        if mode_supports_colors:
            # Consider the first non-black LED color as the device color
            openrgb_off_color = RGBColor(*OFF_COLOR)
            openrgb_color = next(
                (color for color in self.device.colors if color != openrgb_off_color),
                openrgb_off_color,
            )

            if openrgb_color == openrgb_off_color:
                on_by_color = False
            else:
                rgb_color = (
                    openrgb_color.red,
                    openrgb_color.green,
                    openrgb_color.blue,
                )
                # Derive color and brightness from the scaled color
                hsv_color = color_RGB_to_hsv(*rgb_color)
                rgb_color = color_hs_to_RGB(hsv_color[0], hsv_color[1])
                brightness = round(255.0 * (hsv_color[2] / 100.0))

        elif mode is not None:
            # If the current mode is not Off and does not support color, show as white at full brightness
            rgb_color = DEFAULT_COLOR
            brightness = DEFAULT_BRIGHTNESS

        if self._attr_brightness is not None and self._attr_brightness != brightness:
            self._previous_brightness = self._attr_brightness
        if self._attr_rgb_color is not None and self._attr_rgb_color != rgb_color:
            self._previous_rgb_color = self._attr_rgb_color
        if self._mode is not None and self._mode != mode:
            self._previous_mode = self._mode

        self._attr_rgb_color = rgb_color
        self._attr_brightness = brightness
        if mode is None or mode in EFFECT_OFF_OPENRGB_MODES:
            self._attr_effect = EFFECT_OFF
        else:
            self._attr_effect = mode
        self._mode = mode

        if mode is None:
            # If the mode is Off, the light is off
            self._attr_is_on = False
        else:
            self._attr_is_on = on_by_color

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.available:
            self._update_attrs()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return if the light is available."""
        return super().available and self.device_key in self.coordinator.data

    @property
    def device(self) -> Device:
        """Return the OpenRGB device."""
        return self.coordinator.data[self.device_key]

    async def _async_apply_color(
        self, rgb_color: tuple[int, int, int], brightness: int
    ) -> None:
        """Apply the RGB color and brightness to the device."""
        brightness_factor = brightness / 255.0
        scaled_color = RGBColor(
            int(rgb_color[0] * brightness_factor),
            int(rgb_color[1] * brightness_factor),
            int(rgb_color[2] * brightness_factor),
        )

        try:
            await self.coordinator.async_device_set_color(self.device, scaled_color)
        except OpenRGBDisconnected as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_color",
                translation_placeholders={
                    "server_address": self.coordinator.server_address,
                },
            ) from err

    async def _async_apply_mode(self, mode: str) -> None:
        """Apply the given mode to the device."""
        try:
            await self.coordinator.async_device_set_mode(self.device, mode)
        except OpenRGBDisconnected as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_mode",
                translation_placeholders={
                    "server_address": self.coordinator.server_address,
                },
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        mode = None
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            mode = self._preferred_no_effect_mode if effect == EFFECT_OFF else effect
        elif self._mode is None:
            # Restore previous mode when turning on from Off mode
            mode = self._previous_mode or self._preferred_no_effect_mode

        # Check if current or new mode supports colors
        if mode is None:
            # When not applying a new mode, check if the current mode supports color
            mode_supports_color = self._mode in self._supports_color_modes
        else:
            mode_supports_color = mode in self._supports_color_modes

        # Apply color even if switching from Off mode to a color-capable mode
        # because there is no guarantee that the device won't go back to black
        need_to_apply_color = (
            ATTR_RGB_COLOR in kwargs
            or ATTR_BRIGHTNESS in kwargs
            or self._attr_brightness is None
            or self._attr_rgb_color is None
        )

        # If color/brightness parameters require color support but mode doesn't support it,
        # switch to a color-capable mode
        if need_to_apply_color and not mode_supports_color:
            mode = self._preferred_no_effect_mode

        if mode is not None:
            await self._async_apply_mode(mode)

        if need_to_apply_color:
            brightness = None
            if ATTR_BRIGHTNESS in kwargs:
                brightness = kwargs[ATTR_BRIGHTNESS]
            elif self._attr_brightness is None:
                # Restore previous brightness when turning on
                brightness = self._previous_brightness
            if brightness is None:
                # Use default brightness if still None
                brightness = DEFAULT_BRIGHTNESS

            color = None
            if ATTR_RGB_COLOR in kwargs:
                color = kwargs[ATTR_RGB_COLOR]
            elif self._attr_rgb_color is None:
                # Restore previous color when turning on
                color = self._previous_rgb_color
            if color is None:
                # Use default color if still None
                color = DEFAULT_COLOR

            await self._async_apply_color(color, brightness)

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        if self._supports_off_mode:
            await self._async_apply_mode(OPENRGB_MODE_OFF)
        else:
            # If the device does not support Off mode, set color to black
            await self._async_apply_color(OFF_COLOR, 0)

        await self.coordinator.async_refresh()


def check_if_mode_supports_color(mode: ModeData) -> bool:
    """Return True if the mode supports colors."""
    if mode.flags & ModeFlags.HAS_PER_LED_COLOR:
        return True
    @property
    def icon(self) -> str | None:
        """Return an icon for the device_type."""
        icons = {
            DeviceType.MOTHERBOARD: "developer-board",
            DeviceType.DRAM: "memory",
            DeviceType.GPU: "expansion-card",
            DeviceType.COOLER: "fan",
            DeviceType.LEDSTRIP: "led-variant-on",
            DeviceType.KEYBOARD: "keyboard",
            DeviceType.MOUSE: "mouse",
            DeviceType.MOUSEMAT: "rug",
            DeviceType.HEADSET: "headset",
            DeviceType.HEADSET_STAND: "headset-dock",
            DeviceType.GAMEPAD: "gamepad-variant",
            DeviceType.SPEAKER: "speaker",
            DeviceType.STORAGE: "harddisk",
            DeviceType.CASE: "desktop-tower",
            DeviceType.MICROPHONE: "microphone",
            DeviceType.KEYPAD: "dialpad",
        }

        return icons.get(self.device.type)
        DeviceType.MICROPHONE: "microphone",
        DeviceType.KEYPAD: "dialpad",
    }

    return icons.get(device_type)
