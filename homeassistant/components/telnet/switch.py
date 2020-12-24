"""Support for switch controlled using a telnet connection."""
from datetime import timedelta
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_STATE,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCE,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_VALUE_TEMPLATE,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 23
DEFAULT_TIMEOUT = 0.2

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND_OFF): cv.string,
        vol.Required(CONF_COMMAND_ON): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return switches controlled by telnet commands."""
    devices = config.get(CONF_SWITCHES, {})
    switches = []

    for object_id, device_config in devices.items():
        value_template = device_config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        switches.append(
            TelnetSwitch(
                hass,
                object_id,
                device_config.get(CONF_RESOURCE),
                device_config.get(CONF_PORT),
                device_config.get(CONF_NAME, object_id),
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF),
                device_config.get(CONF_COMMAND_STATE),
                value_template,
                device_config.get(CONF_TIMEOUT),
            )
        )

    if not switches:
        _LOGGER.error("No switches added")
        return

    add_entities(switches)


class TelnetSwitch(SwitchEntity):
    """Representation of a switch that can be toggled using telnet commands."""

    def __init__(
        self,
        hass,
        object_id,
        resource,
        port,
        friendly_name,
        command_on,
        command_off,
        command_state,
        value_template,
        timeout,
    ):
        """Initialize the switch."""
        self._hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._resource = resource
        self._port = port
        self._name = friendly_name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template
        self._timeout = timeout

    def _telnet_command(self, command):
        try:
            telnet = telnetlib.Telnet(self._resource, self._port)
            telnet.write(command.encode("ASCII") + b"\r")
            response = telnet.read_until(b"\r", timeout=self._timeout)
            _LOGGER.debug("telnet response: %s", response.decode("ASCII").strip())
            return response.decode("ASCII").strip()
        except OSError as error:
            _LOGGER.error(
                'Command "%s" failed with exception: %s', command, repr(error)
            )
            return None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if no state command is defined, false otherwise."""
        return self._command_state is None

    def update(self):
        """Update device state."""
        response = self._telnet_command(self._command_state)
        if response:
            rendered = self._value_template.render_with_possible_json_value(response)
            self._state = rendered == "True"
        else:
            _LOGGER.warning("Empty response for command: %s", self._command_state)

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._telnet_command(self._command_on)
        if self.assumed_state:
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._telnet_command(self._command_off)
        if self.assumed_state:
            self._state = False
