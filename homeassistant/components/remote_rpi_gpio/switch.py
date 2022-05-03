"""Allows to configure a switch using RPi GPIO."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_PORT, DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_INVERT_LOGIC,
    CONF_PINS,
    DEFAULT_INVERT_LOGIC,
    DEFAULT_PORT,
    PINS_SCHEMA,
)
from .. import remote_rpi_gpio

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PINS): PINS_SCHEMA,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Remote Raspberry PI GPIO devices."""
    address = config[CONF_HOST]
    invert_logic = config[CONF_INVERT_LOGIC]
    port = config[CONF_PORT]
    pins = config[CONF_PINS]

    devices = []
    for pin, name in pins.items():
        try:
            led = remote_rpi_gpio.setup_output(address, port, pin, invert_logic)
        except (ValueError, IndexError, KeyError, OSError):
            return
        new_switch = RemoteRPiGPIOSwitch(name, led)
        devices.append(new_switch)

    add_entities(devices)


class RemoteRPiGPIOSwitch(SwitchEntity):
    """Representation of a Remote Raspberry Pi GPIO."""

    def __init__(self, name, led):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False
        self._switch = led

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """If unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        remote_rpi_gpio.write_output(self._switch, 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        remote_rpi_gpio.write_output(self._switch, 0)
        self._state = False
        self.schedule_update_ha_state()
