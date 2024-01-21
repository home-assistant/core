"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as DEVICE_DOMAIN

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="admin"): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add all entities representing strip sections."""
    # TOD: on the first setup section should be get from the service (sc-rpi)
    async_add_entities([AwesomeLight(entry.entry_id)])


class AwesomeLight(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(self, entry_id: str) -> None:
        """Initialize an AwesomeLight.

        entity_id will be automatically set lower-snake-casing the name of the device
        """
        self._light = None  # light
        self._name = "PEPE PEPE"  # TOD set correct name set from user for instance section 1 section 2 etc slight.name
        self._attr_unique_id = f"{entry_id}-strip-sectionnn"  # TOD set correct entity id for example generating an unique or getting from external service (sc-rpi)
        self._state = None
        self._brightness = 4
        # associate entity to device
        self._attr_device_info = DeviceInfo(identifiers={(DEVICE_DOMAIN, entry_id)})

    @property
    def device_info(self):
        """Return device information about this entity."""
        return self._attr_device_info

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        # self._light.brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        # self._light.turn_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        # self._light.turn_off()

    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        # self._light.update()
        # self._state = self._light.is_on()
        # self._brightness = self._light.brightness
