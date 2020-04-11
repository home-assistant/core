"""
Switch platform integration for Numato USB GPIO expanders.

For more details about this platform, please refer to the documentation at:
https://home-assistant.io/integrations/numato#switch
"""
import logging

from numato_gpio import NumatoGpioError
import voluptuous as vol

import homeassistant.components.numato as numato
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_ID, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["numato"]

CONF_PORTS = "ports"
CONF_DEVICES = "devices"
CONF_INVERT_LOGIC = "invert_logic"

DEFAULT_INVERT_LOGIC = False

_PORTS_SCHEMA = vol.Schema({cv.positive_int: cv.string})
_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_PORTS): _PORTS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)
_DEVICES_SCHEMA = vol.All(list, [_DEVICE_SCHEMA])
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_DEVICES): _DEVICES_SCHEMA})

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the configured Numato USB GPIO switch ports."""

    switches = []
    devices = config.get(CONF_DEVICES)
    for device in devices:
        device_id = device[CONF_ID]
        invert_logic = device[CONF_INVERT_LOGIC]
        ports = device[CONF_PORTS]
        for port_id, port_name in ports.items():
            try:
                switches.append(
                    NumatoGPIOSwitch(port_name, device_id, port_id, invert_logic)
                )
            except NumatoGpioError as ex:
                _LOGGER.error(
                    "Numato USB device %s port %s failed %s",
                    device_id,
                    port_id,
                    str(ex),
                )
    add_devices(switches, True)


class NumatoGPIOSwitch(ToggleEntity):
    """Representation of a Numato USB GPIO switch port."""

    def __init__(self, name, device_id, port, invert_logic):
        """Initialize the port."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        numato.setup_output(self._device_id, self._port)
        numato.write_output(self._device_id, self._port, 1 if self._invert_logic else 0)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if port is turned on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the port on."""
        try:
            numato.write_output(
                self._device_id, self._port, 0 if self._invert_logic else 1
            )
            self._state = True
            self.schedule_update_ha_state()
        except NumatoGpioError as err:
            _LOGGER.error(
                "Failed to turn on Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )

    def turn_off(self, **kwargs):
        """Turn the port off."""
        try:
            numato.write_output(
                self._device_id, self._port, 1 if self._invert_logic else 0
            )
            self._state = False
            self.schedule_update_ha_state()
        except NumatoGpioError as err:
            _LOGGER.error(
                "Failed to turn off Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
