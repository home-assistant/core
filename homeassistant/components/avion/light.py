"""Support for Avion dimmers."""

from __future__ import annotations

import importlib
import time
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an Avion switch."""
    avion = importlib.import_module("avion")

    lights = [
        AvionLight(
            avion.Avion(
                mac=address,
                passphrase=device_config[CONF_API_KEY],
                name=device_config.get(CONF_NAME),
                object_id=device_config.get(CONF_ID),
                connect=False,
            )
        )
        for address, device_config in config[CONF_DEVICES].items()
    ]
    if CONF_USERNAME in config and CONF_PASSWORD in config:
        lights.extend(
            AvionLight(device)
            for device in avion.get_devices(
                config[CONF_USERNAME], config[CONF_PASSWORD]
            )
        )

    add_entities(lights)


class AvionLight(LightEntity):
    """Representation of an Avion light."""

    _attr_support_color_mode = ColorMode.BRIGHTNESS
    _attr_support_color_modes = {ColorMode.BRIGHTNESS}
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_is_on = True

    def __init__(self, device):
        """Initialize the light."""
        self._attr_name = device.name
        self._attr_unique_id = device.mac
        self._attr_brightness = 255
        self._switch = device

    def set_state(self, brightness):
        """Set the state of this lamp to the provided brightness."""
        avion = importlib.import_module("avion")

        # Bluetooth LE is unreliable, and the connection may drop at any
        # time. Make an effort to re-establish the link.
        initial = time.monotonic()
        while True:
            if time.monotonic() - initial >= 10:
                return False
            try:
                self._switch.set_brightness(brightness)
                break
            except avion.AvionException:
                self._switch.connect()
        return True

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        self.set_state(self.brightness)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the specified or all lights off."""
        self.set_state(0)
        self._attr_is_on = False
