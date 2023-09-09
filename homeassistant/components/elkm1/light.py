"""Support for control of ElkM1 lighting (X10, UPB, etc)."""
from __future__ import annotations

from typing import Any

from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.lights import Light

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElkEntity, create_elk_entities
from .const import DOMAIN
from .models import ELKM1Data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elk light platform."""
    elk_data: ELKM1Data = hass.data[DOMAIN][config_entry.entry_id]
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    create_elk_entities(elk_data, elk.lights, "plc", ElkLight, entities)
    async_add_entities(entities)


class ElkLight(ElkEntity, LightEntity):
    """Representation of an Elk lighting device."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _element: Light

    def __init__(self, element: Element, elk: Elk, elk_data: ELKM1Data) -> None:
        """Initialize the Elk light."""
        super().__init__(element, elk, elk_data)
        self._brightness = self._element.status

    @property
    def brightness(self) -> int:
        """Get the brightness."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Get the current brightness."""
        return self._brightness != 0

    def _element_changed(self, element: Element, changeset: Any) -> None:
        status = self._element.status if self._element.status != 1 else 100
        self._brightness = round(status * 2.55)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        self._element.level(round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._element.level(0)
