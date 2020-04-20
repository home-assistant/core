"""
Switch platform integration for Numato USB GPIO expanders.

For more details about this platform, please refer to the documentation at:
https://home-assistant.io/integrations/numato#switch
"""
import logging

from numato_gpio import NumatoGpioError

from homeassistant.const import CONF_ID, CONF_SWITCHES, DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity

from . import DOMAIN, setup_output, write_output

_LOGGER = logging.getLogger(__name__)

CONF_PORTS = "ports"
CONF_DEVICES = "devices"
CONF_INVERT_LOGIC = "invert_logic"


# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the configured Numato USB GPIO switch ports."""

    switches = []
    devices = hass.data[DOMAIN]
    for device in [d for d in devices if CONF_SWITCHES in d]:
        device_id = device[CONF_ID]
        platform = device[CONF_SWITCHES]
        invert_logic = platform[CONF_INVERT_LOGIC]
        ports = platform[CONF_PORTS]
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
        setup_output(self._device_id, self._port)
        write_output(self._device_id, self._port, 1 if self._invert_logic else 0)

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
            write_output(self._device_id, self._port, 0 if self._invert_logic else 1)
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
            write_output(self._device_id, self._port, 1 if self._invert_logic else 0)
            self._state = False
            self.schedule_update_ha_state()
        except NumatoGpioError as err:
            _LOGGER.error(
                "Failed to turn off Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
