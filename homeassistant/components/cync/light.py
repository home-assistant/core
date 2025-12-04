"""Support for Cync light entities."""

from typing import Any

from pycync import CyncLight
from pycync.devices.capabilities import CyncCapability

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    filter_supported_color_modes,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import value_to_brightness
from homeassistant.util.scaling import scale_ranged_value_to_int_range

from .coordinator import CyncConfigEntry, CyncCoordinator
from .entity import CyncBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cync lights from a config entry."""

    coordinator = entry.runtime_data
    cync = coordinator.cync

    entities_to_add = []

    for home in cync.get_homes():
        for room in home.rooms:
            room_lights = [
                CyncLightEntity(device, coordinator, room.name)
                for device in room.devices
                if isinstance(device, CyncLight)
            ]
            entities_to_add.extend(room_lights)

            group_lights = [
                CyncLightEntity(device, coordinator, room.name)
                for group in room.groups
                for device in group.devices
                if isinstance(device, CyncLight)
            ]
            entities_to_add.extend(group_lights)

    async_add_entities(entities_to_add)


class CyncLightEntity(CyncBaseEntity, LightEntity):
    """Representation of a Cync light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_min_color_temp_kelvin = 2000
    _attr_max_color_temp_kelvin = 7000
    _attr_translation_key = "light"
    _attr_name = None

    BRIGHTNESS_SCALE = (0, 100)

    def __init__(
        self,
        device: CyncLight,
        coordinator: CyncCoordinator,
        room_name: str | None = None,
    ) -> None:
        """Set up base attributes."""
        super().__init__(device, coordinator, room_name)

        supported_color_modes = {ColorMode.ONOFF}
        if device.supports_capability(CyncCapability.CCT_COLOR):
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        if device.supports_capability(CyncCapability.DIMMING):
            supported_color_modes.add(ColorMode.BRIGHTNESS)
        if device.supports_capability(CyncCapability.RGB_COLOR):
            supported_color_modes.add(ColorMode.RGB)
        self._attr_supported_color_modes = filter_supported_color_modes(
            supported_color_modes
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        return self._device.is_on

    @property
    def brightness(self) -> int:
        """Provide the light's current brightness."""
        return value_to_brightness(self.BRIGHTNESS_SCALE, self._device.brightness)

    @property
    def color_temp_kelvin(self) -> int:
        """Return color temperature in kelvin."""
        return scale_ranged_value_to_int_range(
            (1, 100),
            (self.min_color_temp_kelvin, self.max_color_temp_kelvin),
            self._device.color_temp,
        )

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Provide the light's current color in RGB format."""
        return self._device.rgb

    @property
    def color_mode(self) -> str | None:
        """Return the active color mode."""

        if (
            self._device.supports_capability(CyncCapability.CCT_COLOR)
            and self._device.color_mode > 0
            and self._device.color_mode <= 100
        ):
            return ColorMode.COLOR_TEMP
        if (
            self._device.supports_capability(CyncCapability.RGB_COLOR)
            and self._device.color_mode == 254
        ):
            return ColorMode.RGB
        if self._device.supports_capability(CyncCapability.DIMMING):
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Process an action on the light."""
        if not kwargs:
            await self._device.turn_on()

        elif kwargs.get(ATTR_COLOR_TEMP_KELVIN) is not None:
            color_temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            converted_color_temp = self._normalize_color_temp(color_temp)

            await self._device.set_color_temp(converted_color_temp)
        elif kwargs.get(ATTR_RGB_COLOR) is not None:
            rgb = kwargs.get(ATTR_RGB_COLOR)

            await self._device.set_rgb(rgb)
        elif kwargs.get(ATTR_BRIGHTNESS) is not None:
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            converted_brightness = self._normalize_brightness(brightness)

            await self._device.set_brightness(converted_brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._device.turn_off()

    def _normalize_brightness(self, brightness: float | None) -> int | None:
        """Return calculated brightness value scaled between 0-100."""
        if brightness is not None:
            return int((brightness / 255) * 100)

        return None

    def _normalize_color_temp(self, color_temp_kelvin: float | None) -> int | None:
        """Return calculated color temp value scaled between 1-100."""
        if color_temp_kelvin is not None:
            kelvin_range = self.max_color_temp_kelvin - self.min_color_temp_kelvin
            scaled_kelvin = int(
                ((color_temp_kelvin - self.min_color_temp_kelvin) / kelvin_range) * 100
            )
            if scaled_kelvin == 0:
                scaled_kelvin += 1

            return scaled_kelvin
        return None

    @property
    def _device(self) -> CyncLight:
        """Fetch the reference to the backing Cync light for this device."""

        return self.coordinator.data[self._cync_device_id]
