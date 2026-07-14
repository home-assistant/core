"""WiZ integration light platform."""

from typing import Any, override

from pywizlight import PilotBuilder
from pywizlight.bulblibrary import BulbClass, BulbType, Features
from pywizlight.scenes import get_id_from_scene_name

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WizConfigEntry, WizData
from .entity import WizToggleEntity

RGB_WHITE_CHANNELS_COLOR_MODE = {1: ColorMode.RGBW, 2: ColorMode.RGBWW}

# TV ambient light products push states without color values or a scene
# while they are synced to the TV
TV_SYNC_MODULES = ("DMORGB", "MHORGB")

# Pseudo effect reported for TV sync products while they are syncing
EFFECT_TV_SYNC = "TV Sync"


def _async_pilot_builder(**kwargs: Any) -> PilotBuilder:
    """Create the PilotBuilder for turn on."""
    brightness = kwargs.get(ATTR_BRIGHTNESS)

    if ATTR_RGBWW_COLOR in kwargs:
        return PilotBuilder(brightness=brightness, rgbww=kwargs[ATTR_RGBWW_COLOR])

    if ATTR_RGBW_COLOR in kwargs:
        return PilotBuilder(brightness=brightness, rgbw=kwargs[ATTR_RGBW_COLOR])

    if ATTR_COLOR_TEMP_KELVIN in kwargs:
        return PilotBuilder(
            brightness=brightness,
            colortemp=kwargs[ATTR_COLOR_TEMP_KELVIN],
        )

    if ATTR_EFFECT in kwargs:
        scene_id = get_id_from_scene_name(kwargs[ATTR_EFFECT])
        if scene_id == 1000:  # rhythm
            return PilotBuilder()
        return PilotBuilder(brightness=brightness, scene=scene_id)

    return PilotBuilder(brightness=brightness)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WiZ Platform from config_flow."""
    if entry.runtime_data.bulb.bulbtype.bulb_type != BulbClass.SOCKET:
        async_add_entities([WizBulbEntity(entry.runtime_data, entry.title)])


class WizBulbEntity(WizToggleEntity, LightEntity):
    """Representation of WiZ Light bulb."""

    _attr_name = None
    _fixed_color_mode: ColorMode | None = None
    _last_color_mode: ColorMode | None = None

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize an WiZLight."""
        super().__init__(wiz_data, name)
        bulb_type: BulbType = self._device.bulbtype
        features: Features = bulb_type.features
        self._is_tv_sync_product = any(
            module in (bulb_type.name or "") for module in TV_SYNC_MODULES
        )
        color_modes = {ColorMode.ONOFF}
        if features.color:
            color_modes.add(RGB_WHITE_CHANNELS_COLOR_MODE[bulb_type.white_channels])
        if features.color_tmp:
            color_modes.add(ColorMode.COLOR_TEMP)
            kelvin = bulb_type.kelvin_range
            self._attr_max_color_temp_kelvin = kelvin.max
            self._attr_min_color_temp_kelvin = kelvin.min
        if features.brightness:
            color_modes.add(ColorMode.BRIGHTNESS)
        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))
        self._attr_effect_list = wiz_data.scenes
        if bulb_type.features.effect:
            self._attr_supported_features = LightEntityFeature.EFFECT
        self._async_update_attrs()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        state = self._device.state

        if (brightness := state.get_brightness()) is not None:
            self._attr_brightness = max(0, min(255, brightness))

        color_modes = self.supported_color_modes
        assert color_modes is not None

        current_mode: ColorMode | None = None
        if ColorMode.COLOR_TEMP in color_modes and (
            color_temp := state.get_colortemp()
        ):
            current_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = color_temp
        elif (
            ColorMode.RGBWW in color_modes and (rgbww := state.get_rgbww()) is not None
        ):
            current_mode = ColorMode.RGBWW
            self._attr_rgbww_color = rgbww
        elif ColorMode.RGBW in color_modes and (rgbw := state.get_rgbw()) is not None:
            current_mode = ColorMode.RGBW
            self._attr_rgbw_color = rgbw
        if current_mode is not None:
            self._attr_color_mode = current_mode
            self._last_color_mode = current_mode

        self._attr_effect = effect = state.get_scene()
        if effect is None and current_mode is None:
            # BRIGHTNESS/ONOFF are only valid color modes while an effect is
            # active, so report a pseudo effect for TV sync products and make
            # sure a supported color mode is always set for other devices
            if (
                self._is_tv_sync_product
                and LightEntityFeature.EFFECT in self.supported_features
            ):
                self._attr_effect = effect = EFFECT_TV_SYNC
            elif self._attr_color_mode not in color_modes:
                # UNKNOWN passes color mode validation and stays reproducible,
                # unlike a value-dependent color mode without its value
                self._attr_color_mode = self._last_color_mode or ColorMode.UNKNOWN
        if effect is not None:
            if brightness is not None:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            else:
                self._attr_color_mode = ColorMode.ONOFF

        super()._async_update_attrs()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if self._is_tv_sync_product and kwargs.get(ATTR_EFFECT) == EFFECT_TV_SYNC:
            # The pseudo effect is not a real scene and cannot be sent
            kwargs.pop(ATTR_EFFECT)
        await self._device.turn_on(_async_pilot_builder(**kwargs))
        await self.coordinator.async_request_refresh()
