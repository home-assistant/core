"""Support for control of ElkM1 lighting (X10, UPB, etc)."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElkEntity, create_elk_entities
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elk light platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[ElkLight] = []
    elk = elk_data["elk"]
    create_elk_entities(elk_data, elk.lights, "plc", ElkLight, entities)
    async_add_entities(entities, True)


class ElkLight(ElkEntity, LightEntity):
    """Representation of an Elk lighting device."""

    def __init__(self, element, elk, elk_data):
        """Initialize the Elk light."""
        super().__init__(element, elk, elk_data)
        self._brightness = self._element.status

    @property
    def brightness(self):
        """Get the brightness."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Get the current brightness."""
        return self._brightness != 0

    def _element_changed(self, element, changeset):
        status = self._element.status if self._element.status != 1 else 100
        self._brightness = round(status * 2.55)

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        self._element.level(round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55))

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        self._element.level(0)
