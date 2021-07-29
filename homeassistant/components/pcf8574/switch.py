"""Support for switch sensor using I2C PCF8574 chip."""
from pcf8574 import PCF8574
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

CONF_I2C_PORT_NUM = "i2c_port_num"
CONF_I2C_ADDRESS = "i2c_address"
CONF_PINS = "pins"
CONF_PULL_MODE = "pull_mode"

DEFAULT_I2C_ADDRESS = 0x20
DEFAULT_I2C_PORT_NUM = 0
CONF_I2C_PORT_NUM = "0"

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_PORT_NUM, default=DEFAULT_I2C_PORT_NUM): vol.Coerce(int),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PCF8574 devices."""
    i2c_address = config.get(CONF_I2C_ADDRESS)
    i2c_port_num = config.get(CONF_I2C_PORT_NUM)

    pcf = PCF8574(i2c_port_num, i2c_address)

    switches = []
    pins = config.get(CONF_PINS)
    for pin_num, pin_name in pins.items():
        switches.append(PCF8574Switch(pcf, pin_name, pin_num))
    add_entities(switches)


class PCF8574Switch(ToggleEntity):
    """Representation of a  PCF8574 output pin."""

    def __init__(self, pcf, name, pin_num):
        """Initialize the pin."""
        self._pcf = pcf
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin_num = pin_num
        self._state = False

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
        return self._pcf[self._pin_num]

    @property
    def assumed_state(self):
        """Return true if optimistic updates are used."""
        return True

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._pcf[self._pin_num] = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._pcf[self._pin_num] = False
        self.schedule_update_ha_state()
