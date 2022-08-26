"""Support for EnOcean light sources."""
from __future__ import annotations

import math
from typing import Any

from enocean.utils import combine_hex, from_hex_string
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .config_flow import CONF_ENOCEAN_DEVICES
from .const import DOMAIN, LOGGER
from .device import EnOceanEntity

CONF_SENDER_ID = "sender_id"

DEFAULT_NAME = "EnOcean Light"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean light platform."""

    LOGGER.warning(
        "Configuring EnOcean via configuration.yaml is deprecated"
        "It will be removed in a future release"
    )

    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)

    add_entities([EnOceanLight(sender_id, dev_id, dev_name)])


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        if device["eep"] == "eltako_fud61npn":
            device_id = from_hex_string(device["id"])
            sender_id = from_hex_string(device["sender_id"])
            async_add_entities([EnOceanLight(sender_id, device_id, device["name"])])


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, sender_id: list[int], dev_id: list[int], dev_name: str) -> None:
        """Initialize the EnOcean light source."""
        super().__init__(dev_id, dev_name)
        self._on_state = False
        self._brightness = 50
        self._sender_id = sender_id
        self._attr_unique_id = f"{combine_hex(dev_id)}"

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.dev_name

    @property
    def brightness(self):
        """Brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._on_state

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on or sets a specific dimmer value."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._brightness = brightness

        bval = math.floor(self._brightness / 256.0 * 100.0)
        if bval == 0:
            bval = 1
        command = [0xA5, 0x02, bval, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light source off."""
        command = [0xA5, 0x02, 0x00, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = False

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._brightness = math.floor(val / 100.0 * 256.0)
            self._on_state = bool(val != 0)
            self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Get device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Eltako",
            "model": "FUD61NPN",
            "sw_version": "",
            "via_device": (DOMAIN, "not yet set"),
        }
