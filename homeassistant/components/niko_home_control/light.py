"""Setup NikoHomeControlLight."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control light platform."""
    hub = hass.data[DOMAIN][entry.entry_id]    
    entities = []
    for action in hub.actions:
        action_type = action.action_type
        if action_type == 1:
            entity = NikoHomeControlLight(action, hub)
            hub.entities.append(entity)
            entities.append(entity)
        if action_type == 2:
            entity = NikoHomeControlDimmableLight(action, hub)
            hub.entities.append(entity)
            entities.append(entity)

    async_add_entities(entities, True)


class NikoHomeControlLight(LightEntity):
    """Representation of an Niko Light."""

    should_poll = False

    def __init__(self, light, hub):
        """Set up the Niko Home Control light platform."""
        self._hub = hub
        self._light = light
        self._attr_name = light.name
        self._attr_is_on = light.is_on
        self._attr_unique_id = f"light-{light.action_id}"
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.action_id)},
            manufacturer=hub.manufacturer,
            name=light.name,
        )

    @property
    def id(self):
        """A Niko Action action_id."""
        return self._light.action_id

    def update_state(self, state):
        """Update HA state."""
        self._attr_is_on = state != 0
        self.publish_updates()

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._light.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._light.remove_callback(self.async_write_ha_state)


class NikoHomeControlDimmableLight(NikoHomeControlLight):
    """Representation of an Niko Dimmable Light."""

    def __init__(self, light, hub):
        """Set up the Niko Home Control Dimmable Light platform."""
        super().__init__(light, hub)

        self._attr_unique_id = f"dimmable-{light.action_id}"
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()
