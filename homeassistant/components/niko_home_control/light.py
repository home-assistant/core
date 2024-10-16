"""Setup NikoHomeControlLight."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

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
        entity = None
        action_type = action.action_type
        if action_type == 1:
            entity = NikoHomeControlLight(action, hub)
        if action_type == 2:
            entity = NikoHomeControlDimmableLight(action, hub)

        if entity:
            hub.entities.append(entity)
            entities.append(entity)

    async_add_entities(entities, True)


class NikoHomeControlLight(LightEntity):
    """Representation of an Niko Light."""

    def __init__(self, light, hub):
        """Set up the Niko Home Control light platform."""
        self._light = light
        self._attr_name = light.name
        self._attr_is_on = light.is_on
        self._attr_unique_id = f"light-{light.action_id}"
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.action_id)},
            manufacturer=hub.manufacturer,
            model=f"{hub.model}-light",
            name=light.name,
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed for a Niko light."""
        return False

    @property
    def id(self):
        """A Niko Action action_id."""
        return self._light.action_id

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()

    def update_state(self, state):
        """Update HA state."""
        _LOGGER.debug("Update state: %s", self.name)
        _LOGGER.debug("State: %s", state)
        self._light.state = state
        self._attr_is_on = state > 0
        self.async_write_ha_state()


class NikoHomeControlDimmableLight(NikoHomeControlLight):
    """Representation of an Niko Dimmable Light."""

    def __init__(self, light, hub):
        """Set up the Niko Home Control Dimmable Light platform."""
        super().__init__(light, hub)
        self._attr_unique_id = f"dimmable-{light.action_id}"
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_brightness = light.state * 2.55

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.action_id)},
            manufacturer=hub.manufacturer,
            model=f"{hub.model}-dimmable-light",
            name=light.name,
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        _LOGGER.debug("Brightness: %s", kwargs.get(ATTR_BRIGHTNESS, 255))
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()

    def update_state(self, state):
        """Update HA state."""
        _LOGGER.debug("Update state: %s", self.name)
        _LOGGER.debug("State: %s", state)
        self._light.state = state
        self._attr_is_on = state > 0
        self._attr_brightness = state * 2.55
        self.async_write_ha_state()
