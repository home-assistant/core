"""Lights on Zigbee Home Automation networks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import light
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import get_zha_data

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


class Light(light.LightEntity, ZHAEntity):
    """Representation of a ZHA or ZLL light."""

    _attr_supported_color_modes: set[ColorMode]
    _attr_translation_key: str = "light"

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the light."""
        super().__init__(*args, **kwargs)
        self._attr_min_mireds: int = self.entity_data.entity.min_mireds
        self._attr_max_mireds: int = self.entity_data.entity.max_mireds
        self._attr_color_mode = self.entity_data.entity.color_mode
        self._attr_supported_features: LightEntityFeature = LightEntityFeature(
            self.entity_data.entity.supported_features.value
        )
        self._attr_effect_list: list[str] | None = self.entity_data.entity.effect_list
        self._attr_supported_color_modes = (
            self.entity_data.entity._supported_color_modes
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        self._async_unsub_transition_listener()
        await super().async_will_remove_from_hass()

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(**kwargs)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_on(**kwargs)
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
