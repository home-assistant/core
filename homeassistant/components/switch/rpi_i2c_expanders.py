"""
Allows to configure a switch using RPi I²C bus connected expanders.
"""

import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['rpi_i2c_expanders']

# TODO: Merge in components.rpi_i2c_expanders ?
i2c_bus_port = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

_CHIP_SCHEMA = vol.Schema({
    vol.Required("hw"): cv.string,
    vol.Required("ports"): _SWITCHES_SCHEMA,
    vol.Optional("invert_logic_ports"): [cv.positive_int],
})

_CHIPS_SCHEMA = vol.Schema({
    i2c_bus_port: _CHIP_SCHEMA,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("chips"): _CHIPS_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up """
    import homeassistant.components.rpi_i2c_expanders

    managed_chips = homeassistant.components.rpi_i2c_expanders.g_managed_chips

    switches = []
    chips = config.get("chips")

    ## log.info("chips: %r", chips)
    for address, chip in chips.items():
        ## _LOGGER.info("address: %r chip: %r", address, chip)
        chip_id = chip["hw"]
        invert_logic_ports = chip.get('invert_logic_ports', ())
        managed_chip = managed_chips.manage_chip(address, chip_id)
        _LOGGER.debug("address: %r chip_id: %r -> managed_chip: %r, invert_logic_ports: %r",
                      address, chip_id,  managed_chip, invert_logic_ports, )
        for pin, name in chip["ports"].items():
            invert_logic = pin in invert_logic_ports
            expander_switch = ExpanderSwitch(name, managed_chip, invert_logic)
            managed_chip.pin_connect(pin, expander_switch)
            switches.append(expander_switch)
            _LOGGER.debug("address: %r managed_chip: %r: pin: %r connected to expander_switch: %r",
                          address, managed_chip, pin, expander_switch, )
        managed_chip.ha_configure()  # HW configuration of chip.
        managed_chip.update_outputs()  # Set initial states.

    add_devices(switches)


class ExpanderSwitch(ToggleEntity):
    """Representation of a Raspberry Pi I²C bus expander IO based switch."""

    def __init__(self, name, ha_expander, invert_logic):
        """Initialize the pin."""
        self._name = name
        self._state = False
        self._ha_expander = ha_expander  # HAExpander
        self._invert_logic = bool(invert_logic)

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
        """Return true if device is on."""
        return self._state

    @property
    def is_pin_high(self):
        """Return true if pin state should be high."""
        return self._state != self._invert_logic

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        self._ha_expander.update_outputs()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self._ha_expander.update_outputs()
        self.schedule_update_ha_state()
