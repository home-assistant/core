"""Support for wake on lan."""
import logging
import platform
import subprocess as sp

import voluptuous as vol
import wakeonlan

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

CONF_OFF_ACTION = "turn_off"

DEFAULT_NAME = "Wake on LAN"
DEFAULT_PING_TIMEOUT = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a wake on lan switch."""
    broadcast_address = config.get(CONF_BROADCAST_ADDRESS)
    broadcast_port = config.get(CONF_BROADCAST_PORT)
    host = config.get(CONF_HOST)
    mac_address = config[CONF_MAC]
    name = config[CONF_NAME]
    off_action = config.get(CONF_OFF_ACTION)

    add_entities(
        [
            WolSwitch(
                hass,
                name,
                host,
                mac_address,
                off_action,
                broadcast_address,
                broadcast_port,
            )
        ],
        True,
    )


class WolSwitch(SwitchEntity):
    """Representation of a wake on lan switch."""

    def __init__(
        self,
        hass,
        name,
        host,
        mac_address,
        off_action,
        broadcast_address,
        broadcast_port,
    ):
        """Initialize the WOL switch."""
        self._hass = hass
        self._name = name
        self._host = host
        self._mac_address = mac_address
        self._broadcast_address = broadcast_address
        self._broadcast_port = broadcast_port
        self._off_script = Script(hass, off_action) if off_action else None
        self._state = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if self._broadcast_address:
            wakeonlan.send_magic_packet(
                self._mac_address,
                ip_address=self._broadcast_address,
                port=self._broadcast_port,
            )
        else:
            wakeonlan.send_magic_packet(self._mac_address)

    def turn_off(self, **kwargs):
        """Turn the device off if an off action is present."""
        if self._off_script is not None:
            self._off_script.run()

    def update(self):
        """Check if device is on and update the state."""
        if platform.system().lower() == "windows":
            ping_cmd = [
                "ping",
                "-n",
                "1",
                "-w",
                str(DEFAULT_PING_TIMEOUT * 1000),
                str(self._host),
            ]
        else:
            ping_cmd = [
                "ping",
                "-c",
                "1",
                "-W",
                str(DEFAULT_PING_TIMEOUT),
                str(self._host),
            ]

        status = sp.call(ping_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        self._state = not bool(status)
