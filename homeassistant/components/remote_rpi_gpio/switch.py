"""Allows to configure a switch using RPi GPIO."""
import logging

from gpiozero import LED
from gpiozero.pins.pigpio import PiGPIOFactory
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

from . import CONF_INVERT_LOGIC, DEFAULT_INVERT_LOGIC

_LOGGER = logging.getLogger(__name__)

CONF_PORTS = "ports"

_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)


def setup_switch(address, port, name, invert_logic=False):
    """Set up a switch."""
    _LOGGER.debug(
        "setting up output %s on %s port %s %s",
        name,
        address,
        port,
        "inverted" if invert_logic else "",
    )
    led = LED(port, active_high=not invert_logic, pin_factory=PiGPIOFactory(address))
    new_switch = RemoteRPiGPIOSwitch(name, led)
    return new_switch


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Remote Raspberry PI GPIO devices."""
    address = config[CONF_HOST]
    invert_logic = config[CONF_INVERT_LOGIC]
    ports = config[CONF_PORTS]

    devices = []
    for port, name in ports.items():
        try:

            new_switch = setup_switch(address, port, name, invert_logic)
            devices.append(new_switch)
        except (ValueError, IndexError, KeyError, OSError):
            return

    add_entities(devices)


class RemoteRPiGPIOSwitch(SwitchEntity):
    """Representation of a Remtoe Raspberry Pi GPIO."""

    def __init__(self, name, led):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
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
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._switch.is_lit

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.debug("turn on switch %s %s", self._name, self._switch.pin)
        self._switch.on()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("turn off switch %s %s", self._name, self._switch.pin)
        self._switch.off()
        self.schedule_update_ha_state()
