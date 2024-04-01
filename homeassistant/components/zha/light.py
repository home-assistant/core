"""Lights on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
import logging
from typing import Any

from homeassistant.components import light
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation light from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.LIGHT, [])
    entities = [Light(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Light, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class Light(light.LightEntity, ZHAEntity):
    """Representation of a ZHA or ZLL light."""

    def __init__(self, entity_data: Any) -> None:
        """Initialize the ZHA light."""
        super().__init__(entity_data)
        self._attr_supported_color_modes: set[ColorMode] = set()
        for color_mode in self.entity_data.entity.supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode(color_mode))
        self._attr_supported_features = LightEntityFeature(
            self.entity_data.entity.supported_features
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        attributes = {
            "off_with_transition": self.entity_data.entity._off_with_transition,
            "off_brightness": self.entity_data.entity._off_brightness,
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
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value [int, int]."""
        return self.entity_data.entity.hs_color

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self.entity_data.entity.xy_color

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        return self.entity_data.entity.color_temp

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode."""
        return ColorMode(self.entity_data.entity.color_mode)

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self.entity_data.entity.effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self.entity_data.entity.effect

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(**kwargs)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off(**kwargs)
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._attr_state = last_state.state == STATE_ON
        if "brightness" in last_state.attributes:
            self._attr_brightness = last_state.attributes["brightness"]
        if "off_with_transition" in last_state.attributes:
            self._off_with_transition = last_state.attributes["off_with_transition"]
        if "off_brightness" in last_state.attributes:
            self._off_brightness = last_state.attributes["off_brightness"]
        if (color_mode := last_state.attributes.get("color_mode")) is not None:
            self._attr_color_mode = ColorMode(color_mode)
        if "color_temp" in last_state.attributes:
            self._attr_color_temp = last_state.attributes["color_temp"]
        if "xy_color" in last_state.attributes:
            self._attr_xy_color = last_state.attributes["xy_color"]
        if "hs_color" in last_state.attributes:
            self._attr_hs_color = last_state.attributes["hs_color"]
        if "effect" in last_state.attributes:
            self._attr_effect = last_state.attributes["effect"]
