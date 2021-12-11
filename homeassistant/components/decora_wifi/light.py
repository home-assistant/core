"""Interfaces with the myLeviton API for Decora Smart WiFi products."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import DecoraWifiEntity, DecoraWifiPlatform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Validation of the user's yaml configuration schema
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Decora Wifi Platform from yaml."""
    # Trigger import config flow
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Decora Wifi lights based on a config entry."""
    # Retrieve the platform session from the reference stored in data.
    session: DecoraWifiPlatform = hass.data[DOMAIN][entry.entry_id]
    lights = session.lights

    async_add_entities([DecoraWifiLight(light) for light in lights], True)


class DecoraWifiLight(DecoraWifiEntity, LightEntity):
    """Representation of a Decora WiFi switch."""

    @property
    def supported_features(self):
        """Return supported features."""
        if self._switch.canSetLevel:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        return 0

    @property
    def brightness(self):
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.power == "ON"

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on & adjust brightness."""
        attribs = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            max_level = self._switch.data.get("maxLevel", 100)
            min_level = self._switch.data.get("minLevel", 0)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * max_level / 255)
            brightness = max(brightness, min_level)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION])
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    def update(self):
        """Fetch new state data for this switch."""
        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
