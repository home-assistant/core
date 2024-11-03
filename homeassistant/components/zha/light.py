"""Lights on Zigbee Home Automation networks."""

from __future__ import annotations

from collections.abc import Mapping
import functools
import logging
from typing import Any

from zha.application.platforms.light.const import (
    ColorMode as ZhaColorMode,
    LightEntityFeature as ZhaLightEntityFeature,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
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
    async_add_entities: AddEntitiesCallback,
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


class Light(LightEntity, ZHAEntity):
    """Representation of a ZHA or ZLL light."""

    def __init__(self, entity_data: EntityData) -> None:
        """Initialize the ZHA light."""
        super().__init__(entity_data)
        color_modes: set[ColorMode] = set()
        has_brightness = False
        for color_mode in self.entity_data.entity.supported_color_modes:
            if color_mode == ZhaColorMode.BRIGHTNESS:
                has_brightness = True
            if color_mode not in (ZhaColorMode.BRIGHTNESS, ZhaColorMode.ONOFF):
                color_modes.add(ZHA_TO_HA_COLOR_MODE[color_mode])
        if color_modes:
            self._attr_supported_color_modes = color_modes
        elif has_brightness:
            color_modes.add(ColorMode.BRIGHTNESS)
            self._attr_supported_color_modes = color_modes
        else:
            color_modes.add(ColorMode.ONOFF)
            self._attr_supported_color_modes = color_modes

        features = LightEntityFeature(0)
        zha_features: ZhaLightEntityFeature = self.entity_data.entity.supported_features

        if ZhaLightEntityFeature.EFFECT in zha_features:
            features |= LightEntityFeature.EFFECT
        if ZhaLightEntityFeature.FLASH in zha_features:
            features |= LightEntityFeature.FLASH
        if ZhaLightEntityFeature.TRANSITION in zha_features:
            features |= LightEntityFeature.TRANSITION

        self._attr_supported_features = features

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        state = self.entity_data.entity.state
        return {
            "off_with_transition": state.get("off_with_transition"),
            "off_brightness": state.get("off_brightness"),
        }

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return self.entity_data.entity.is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light."""
        return self.entity_data.entity.brightness

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self.entity_data.entity.min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self.entity_data.entity.max_mireds

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self.entity_data.entity.xy_color

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        return self.entity_data.entity.color_temp

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode."""
        if self.entity_data.entity.color_mode is None:
            return None
        return ZHA_TO_HA_COLOR_MODE[self.entity_data.entity.color_mode]

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self.entity_data.entity.effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self.entity_data.entity.effect

    @convert_zha_error_to_ha_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(
            transition=kwargs.get(ATTR_TRANSITION),
            brightness=kwargs.get(ATTR_BRIGHTNESS),
            effect=kwargs.get(ATTR_EFFECT),
            flash=kwargs.get(ATTR_FLASH),
            color_temp=kwargs.get(ATTR_COLOR_TEMP),
            xy_color=kwargs.get(ATTR_XY_COLOR),
        )
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off(
            transition=kwargs.get(ATTR_TRANSITION)
        )
        self.async_write_ha_state()

    @callback
    def restore_external_state_attributes(self, state: State) -> None:
        """Restore entity state."""
        self.entity_data.entity.restore_external_state_attributes(
            state=(state.state == STATE_ON),
            off_with_transition=state.attributes.get(OFF_WITH_TRANSITION),
            off_brightness=state.attributes.get(OFF_BRIGHTNESS),
            brightness=state.attributes.get(ATTR_BRIGHTNESS),
            color_temp=state.attributes.get(ATTR_COLOR_TEMP),
            xy_color=state.attributes.get(ATTR_XY_COLOR),
            color_mode=(
                HA_TO_ZHA_COLOR_MODE[ColorMode(state.attributes[ATTR_COLOR_MODE])]
                if state.attributes.get(ATTR_COLOR_MODE) is not None
                else None
            ),
            effect=state.attributes.get(ATTR_EFFECT),
        )
