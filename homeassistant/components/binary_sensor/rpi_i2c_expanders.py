"""
Support for binary sensor based on  I²C port expanders

Example configuration:

binary_sensor:
  - platform: rpi_gpio
    ports:
      17: GPIO17
  - platform: rpi_i2c_expanders
    chips:
        0x20:
           hw: MCP23018
           ports:
               6: P20_IN_6
           invert_logic_ports: [ 6, ]
        0x24:
            hw: PCF8574
            ports:
                7: P24_IN_7
            invert_logic_ports: [ 7, ]

"""

# TODO:
# For more details about this component, please refer to the documentation at
# https://home-assistant.io/components/TODO/


import logging

import voluptuous as vol

from homeassistant.components import rpi_i2c_expanders
import homeassistant.helpers.config_validation as cv

from homeassistant.components.binary_sensor import (
    BinarySensorDevice,
    PLATFORM_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["rpi_i2c_expanders"]


# TODO: Merge in components.rpi_i2c_expanders ?
i2c_bus_port = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

_CHIP_SCHEMA = vol.Schema(
    {
        vol.Required("hw"): cv.string,
        vol.Required("ports"): _SWITCHES_SCHEMA,
        vol.Optional("invert_logic_ports"): [cv.positive_int],
    }
)

_CHIPS_SCHEMA = vol.Schema({i2c_bus_port: _CHIP_SCHEMA})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required("chips"): _CHIPS_SCHEMA}
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup RPi I²C based I/O expanders."""

    import homeassistant.components.rpi_i2c_expanders

    managed_chips = homeassistant.components.rpi_i2c_expanders.g_managed_chips
    sensors = []
    chips = config.get("chips")

    for address, chip in chips.items():
        chip_id = chip["hw"]
        invert_logic_ports = chip.get("invert_logic_ports", ())
        managed_chip = managed_chips.manage_chip(address, chip_id)
        _LOGGER.debug(
            "address: 0x%x chip_id: %r -> managed_chip: %r,"
            " invert_logic_ports: %r",
            address,
            chip_id,
            managed_chip,
            invert_logic_ports,
        )
        for pin, name in chip["ports"].items():
            invert_logic = pin in invert_logic_ports
            expander_sensor = ExpanderSensor(name, managed_chip, invert_logic)
            managed_chip.pin_connect(pin, expander_sensor)
            sensors.append(expander_sensor)
            _LOGGER.debug(
                "address: 0x%x managed_chip: %r: pin: %r "
                "connected to expander sensor: %r",
                address,
                managed_chip,
                pin,
                expander_sensor,
            )
        managed_chip.ha_configure()  # HW configuration of chip

    # NOTE: Seems g_pollwatcher is not yet set up
    add_devices(sensors)
    _LOGGER.info("rpi_i2c_expanders setup finished")


class ExpanderSensor(BinarySensorDevice):
    """Representation of a sensor based on Expander."""

    def __init__(self, name, ha_expander, invert_logic):
        """Initialize the sensor."""
        self._name = name
        self._ha_expander = ha_expander  # HAExpander
        self._invert_logic = bool(invert_logic)
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # self._state = 1
        pass

    def set_state(self, new_state):
        self._state = new_state
