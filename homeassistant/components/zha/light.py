"""Lights on Zigbee Home Automation networks."""

from collections.abc import Mapping
import functools
import logging
from typing import Any, override

from zha.application.platforms.light.const import (
    ColorMode as ZhaColorMode,
    LightEntityFeature as ZhaLightEntityFeature,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    LightEntityStateAttribute,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from .entity import ZHASupportedFeaturesEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)

ZHA_TO_HA_COLOR_MODE = {
    ZhaColorMode.UNKNOWN: ColorMode.UNKNOWN,
    ZhaColorMode.ONOFF: ColorMode.ONOFF,
    ZhaColorMode.BRIGHTNESS: ColorMode.BRIGHTNESS,
    ZhaColorMode.COLOR_TEMP: ColorMode.COLOR_TEMP,
    ZhaColorMode.XY: ColorMode.XY,
}

HA_TO_ZHA_COLOR_MODE = {v: k for k, v in ZHA_TO_HA_COLOR_MODE.items()}

OFF_BRIGHTNESS = "off_brightness"
OFF_WITH_TRANSITION = "off_with_transition"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation light from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.LIGHT]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Light, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class Light(LightEntity, ZHASupportedFeaturesEntity):
    """Representation of a ZHA or ZLL light."""

    @staticmethod
    @functools.cache
    @override
    def _convert_supported_features(
        zha_features: ZhaLightEntityFeature,
    ) -> LightEntityFeature:
        """Convert ZHA light features to HA light features."""
        features = LightEntityFeature(0)

        if ZhaLightEntityFeature.EFFECT in zha_features:
            features |= LightEntityFeature.EFFECT
        if ZhaLightEntityFeature.FLASH in zha_features:
            features |= LightEntityFeature.FLASH
        if ZhaLightEntityFeature.TRANSITION in zha_features:
            features |= LightEntityFeature.TRANSITION

        return features

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability attributes from the cached state."""
        super()._update_capability_attrs()
        state = self._zha_state

        color_modes: set[ColorMode] = set()
        has_brightness = False
        for color_mode in state.supported_color_modes:
            if color_mode == ZhaColorMode.BRIGHTNESS:
                has_brightness = True
            if color_mode not in (ZhaColorMode.BRIGHTNESS, ZhaColorMode.ONOFF):
                color_modes.add(ZHA_TO_HA_COLOR_MODE[color_mode])
        if not color_modes:
            color_modes.add(ColorMode.BRIGHTNESS if has_brightness else ColorMode.ONOFF)
        self._attr_supported_color_modes = color_modes

        self._attr_max_color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
            state.min_mireds
        )
        self._attr_min_color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
            state.max_mireds
        )
        self._attr_effect_list = state.effect_list

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        state = self._zha_state
        return {
            "off_with_transition": state.off_with_transition,
            "off_brightness": state.off_brightness,
        }

    @property
    @override
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return self._zha_state.on

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light."""
        return self._zha_state.brightness

    @property
    @override
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self._zha_state.xy_color

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        return (
            color_util.color_temperature_mired_to_kelvin(mireds)
            if (mireds := self._zha_state.color_temp)
            else None
        )

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode."""
        if self._zha_state.color_mode is None:
            return ColorMode.UNKNOWN
        return ZHA_TO_HA_COLOR_MODE[self._zha_state.color_mode]

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._zha_state.effect

    @convert_zha_error_to_ha_error()
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        color_temp = (
            color_util.color_temperature_kelvin_to_mired(color_temp_k)
            if (color_temp_k := kwargs.get(ATTR_COLOR_TEMP_KELVIN))
            else None
        )
        await self.entity_data.entity.async_turn_on(
            transition=kwargs.get(ATTR_TRANSITION),
            brightness=kwargs.get(ATTR_BRIGHTNESS),
            effect=kwargs.get(ATTR_EFFECT),
            flash=kwargs.get(ATTR_FLASH),
            color_temp=color_temp,
            xy_color=kwargs.get(ATTR_XY_COLOR),
        )
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off(
            transition=kwargs.get(ATTR_TRANSITION)
        )
        self.async_write_ha_state()

    @callback
    @override
    def restore_external_state_attributes(self, state: State) -> None:
        """Restore entity state."""
        color_temp = (
            color_util.color_temperature_kelvin_to_mired(color_temp_k)
            if (
                color_temp_k := state.attributes.get(
                    LightEntityStateAttribute.COLOR_TEMP_KELVIN
                )
            )
            else None
        )
        self.entity_data.entity.restore_external_state_attributes(
            state=(state.state == STATE_ON),
            off_with_transition=state.attributes.get(OFF_WITH_TRANSITION),
            off_brightness=state.attributes.get(OFF_BRIGHTNESS),
            brightness=state.attributes.get(LightEntityStateAttribute.BRIGHTNESS),
            color_temp=color_temp,
            xy_color=state.attributes.get(LightEntityStateAttribute.XY_COLOR),
            color_mode=(
                HA_TO_ZHA_COLOR_MODE[
                    ColorMode(state.attributes[LightEntityStateAttribute.COLOR_MODE])
                ]
                if state.attributes.get(LightEntityStateAttribute.COLOR_MODE)
                is not None
                else None
            ),
            effect=state.attributes.get(LightEntityStateAttribute.EFFECT),
        )
