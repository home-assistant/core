"""WiZ integration."""
from __future__ import annotations

import logging
from typing import Any

from pywizlight import PilotBuilder
from pywizlight.bulblibrary import BulbClass, BulbType
from pywizlight.rgbcw import convertHSfromRGBCW
from pywizlight.scenes import get_id_from_scene_name

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import DOMAIN
from .entity import WizToggleEntity
from .models import WizData

_LOGGER = logging.getLogger(__name__)

DEFAULT_COLOR_MODES = {COLOR_MODE_HS, COLOR_MODE_COLOR_TEMP}
DEFAULT_MIN_MIREDS = 153
DEFAULT_MAX_MIREDS = 454


def get_supported_color_modes(bulb_type: BulbType) -> set[str]:
    """Flag supported features."""
    color_modes = set()
    features = bulb_type.features
    if features.color:
        color_modes.add(COLOR_MODE_HS)
    if features.color_tmp:
        color_modes.add(COLOR_MODE_COLOR_TEMP)
    if not color_modes and features.brightness:
        color_modes.add(COLOR_MODE_BRIGHTNESS)
    return color_modes


def supports_effects(bulb_type: BulbType) -> bool:
    """Check if a bulb supports effects."""
    return bool(bulb_type.features.effect)


def get_min_max_mireds(bulb_type: BulbType) -> tuple[int, int]:
    """Return the coldest and warmest color_temp that this light supports."""
    # DW bulbs have no kelvin
    if bulb_type.bulb_type == BulbClass.DW:
        return 0, 0
    # If bulbtype is TW or RGB then return the kelvin value
    return color_temperature_kelvin_to_mired(
        bulb_type.kelvin_range.max
    ), color_temperature_kelvin_to_mired(bulb_type.kelvin_range.min)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WiZ Platform from config_flow."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WizBulbEntity(wiz_data, entry.title)])


class WizBulbEntity(WizToggleEntity, LightEntity):
    """Representation of WiZ Light bulb."""

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize an WiZLight."""
        super().__init__(wiz_data, name)
        bulb_type: BulbType = self._device.bulbtype
        self._attr_effect_list = wiz_data.scenes
        self._attr_min_mireds, self._attr_max_mireds = get_min_max_mireds(bulb_type)
        self._attr_supported_color_modes = get_supported_color_modes(bulb_type)
        if supports_effects(bulb_type):
            self._attr_supported_features = SUPPORT_EFFECT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        state = self._device.state
        if (brightness := state.get_brightness()) is not None:
            self._attr_brightness = max(0, min(255, brightness))
        color_modes = self.supported_color_modes
        assert color_modes is not None
        if COLOR_MODE_COLOR_TEMP in color_modes and state.get_colortemp() is not None:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
            if color_temp := state.get_colortemp():
                self._attr_color_temp = color_temperature_kelvin_to_mired(color_temp)
        elif (
            COLOR_MODE_HS in color_modes
            and (rgb := state.get_rgb()) is not None
            and rgb[0] is not None
        ):
            if (warm_white := state.get_warm_white()) is not None:
                self._attr_hs_color = convertHSfromRGBCW(rgb, warm_white)
            self._attr_color_mode = COLOR_MODE_HS
        else:
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        self._attr_effect = state.get_scene()
        super()._handle_coordinator_update()

    def _async_pilot_builder(self, **kwargs: Any) -> PilotBuilder:
        """Create the PilotBuilder for turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if ATTR_RGB_COLOR in kwargs:
            return PilotBuilder(rgb=kwargs[ATTR_RGB_COLOR], brightness=brightness)

        if ATTR_HS_COLOR in kwargs:
            return PilotBuilder(
                hucolor=(kwargs[ATTR_HS_COLOR][0], kwargs[ATTR_HS_COLOR][1]),
                brightness=brightness,
            )

        colortemp = None
        if ATTR_COLOR_TEMP in kwargs:
            colortemp = color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])

        sceneid = None
        if ATTR_EFFECT in kwargs:
            sceneid = get_id_from_scene_name(kwargs[ATTR_EFFECT])

        if sceneid == 1000:  # rhythm
            return PilotBuilder()

        _LOGGER.debug(
            "[wizlight %s] Pilot will be send with brightness=%s, colortemp=%s, scene=%s",
            self._device.ip,
            brightness,
            colortemp,
            sceneid,
        )
        return PilotBuilder(brightness=brightness, colortemp=colortemp, scene=sceneid)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self._device.turn_on(self._async_pilot_builder(**kwargs))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._device.turn_off()
        await self.coordinator.async_request_refresh()
