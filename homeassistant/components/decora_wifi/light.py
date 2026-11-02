"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

from datetime import timedelta
import logging
from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from . import DecoraWifiConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DecoraWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Decora WiFi lights from a config entry."""
    async_add_entities(
        DecoraWifiLight(switch) for switch in entry.runtime_data.switches
    )


class DecoraWifiLight(LightEntity):
    """Representation of a Decora WiFi switch."""

    def __init__(self, switch):
        """Initialize the switch."""
        self._switch = switch
        self._attr_unique_id = switch.serial

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._switch.canSetLevel:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    @override
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        if self._switch.canSetLevel:
            return LightEntityFeature.TRANSITION
        return LightEntityFeature(0)

    @property
    @override
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    @override
    def unique_id(self):
        """Return the ID of this light."""
        return self._switch.serial

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    @override
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._switch.power == "ON"

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on & adjust brightness."""
        attribs: dict[str, Any] = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            min_level = self._switch.data.get("minLevel", 0)
            max_level = self._switch.data.get("maxLevel", 100)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * max_level / 255)
            brightness = max(brightness, min_level)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION])
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        try:
            self._switch.update_attributes(attribs)
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_failed",
            ) from err

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}
        try:
            self._switch.update_attributes(attribs)
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_failed",
            ) from err

    @Throttle(timedelta(seconds=30))
    def update(self) -> None:
        """Fetch new state data for this switch."""
        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
