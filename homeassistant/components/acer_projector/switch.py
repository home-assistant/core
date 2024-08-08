"""Use serial protocol of Acer projector to obtain state of the projector."""

from __future__ import annotations

import logging
import re
from typing import Any

import serial
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_FILENAME,
    CONF_NAME,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CMD_DICT,
    CONF_WRITE_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    ECO_MODE,
    ICON,
    INPUT_SOURCE,
    LAMP,
    LAMP_HOURS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.isdevice,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(
            CONF_WRITE_TIMEOUT, default=DEFAULT_WRITE_TIMEOUT
        ): cv.positive_int,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Connect with serial port and return Acer Projector."""
    serial_port = config[CONF_FILENAME]
    name = config[CONF_NAME]
    timeout = config[CONF_TIMEOUT]
    write_timeout = config[CONF_WRITE_TIMEOUT]

    add_entities([AcerSwitch(serial_port, name, timeout, write_timeout)], True)


class AcerSwitch(SwitchEntity):
    """Represents an Acer Projector as a switch."""

    _attr_icon = ICON

    def __init__(
        self,
        serial_port: str,
        name: str,
        timeout: int,
        write_timeout: int,
    ) -> None:
        """Init of the Acer projector."""
        self.ser = serial.Serial(
            port=serial_port, timeout=timeout, write_timeout=write_timeout
        )
        self._serial_port = serial_port
        self._attr_name = name
        self._attributes = {
            LAMP_HOURS: STATE_UNKNOWN,
            INPUT_SOURCE: STATE_UNKNOWN,
            ECO_MODE: STATE_UNKNOWN,
        }

    def _write_read(self, msg: str) -> str:
        """Write to the projector and read the return."""
        ret = ""
        # Sometimes the projector won't answer for no reason or the projector
        # was disconnected during runtime.
        # This way the projector can be reconnected and will still work
        try:
            if not self.ser.is_open:
                self.ser.open()
            self.ser.write(msg.encode("utf-8"))
            # Size is an experience value there is no real limit.
            # AFAIK there is no limit and no end character so we will usually
            # need to wait for timeout
            ret = self.ser.read_until(size=20).decode("utf-8")
        except serial.SerialException:
            _LOGGER.error("Problem communicating with %s", self._serial_port)
        self.ser.close()
        return ret

    def _write_read_format(self, msg: str) -> str:
        """Write msg, obtain answer and format output."""
        # answers are formatted as ***\answer\r***
        awns = self._write_read(msg)
        if match := re.search(r"\r(.+)\r", awns):
            return match.group(1)
        return STATE_UNKNOWN

    def update(self) -> None:
        """Get the latest state from the projector."""
        awns = self._write_read_format(CMD_DICT[LAMP])
        if awns == "Lamp 1":
            self._attr_is_on = True
            self._attr_available = True
        elif awns == "Lamp 0":
            self._attr_is_on = False
            self._attr_available = True
        else:
            self._attr_available = False

        for key in self._attributes:
            if msg := CMD_DICT.get(key):
                awns = self._write_read_format(msg)
                self._attributes[key] = awns
        self._attr_extra_state_attributes = self._attributes

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""
        msg = CMD_DICT[STATE_ON]
        self._write_read(msg)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""
        msg = CMD_DICT[STATE_OFF]
        self._write_read(msg)
        self._attr_is_on = False
