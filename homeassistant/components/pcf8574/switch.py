"""Support for switch sensor using I2C PCF8574 chip."""
from pcf8574 import PCF8574
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

from .const import DOMAIN

CONF_I2C_PORT_NUM = "i2c_port_num"
CONF_I2C_ADDRESS = "i2c_address"
CONF_PINS = "pins"
CONF_INVERT_LOGIC = "invert_logic"

DEFAULT_NAME = "PCF8574 Switch"
DEFAULT_I2C_ADDRESS = 0x20
DEFAULT_I2C_PORT_NUM = 0
DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_PORT_NUM, default=DEFAULT_I2C_PORT_NUM): vol.Coerce(int),
    }
)


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up switch from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if config_entry.options:
        config.update(config_entry.options)

    invert_logic = config.get(CONF_INVERT_LOGIC, DEFAULT_INVERT_LOGIC)
    switches = []
    for i in range(8):
        # try to get all switch names. if key exist also the switch exists
        switch_name = config.get(f"switch_{i+1}_name")
        if switch_name is not None:
            switches.append(
                PCF8574Switch(
                    config["i2c_port_num"],
                    config["i2c_address"],
                    switch_name,
                    i,
                    invert_logic,
                    config_entry.entry_id,
                )
            )
    async_add_entities(switches, update_before_add=True)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PCF8574 devices."""
    i2c_address = config.get(CONF_I2C_ADDRESS)
    i2c_port_num = config.get(CONF_I2C_PORT_NUM)
    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    pins = config.get(CONF_PINS)
    for pin_num, pin_name in pins.items():
        switches.append(
            PCF8574Switch(
                i2c_port_num,
                i2c_address,
                pin_name,
                pin_num,
                invert_logic,
            )
        )
    add_entities(switches)


class PCF8574Switch(ToggleEntity):
    """Representation of a PCF8574 output pin."""

    def __init__(
        self, i2c_port_num, i2c_address, name, pin_num, invert_logic, unique_id=None
    ):
        """Initialize the pin."""
        self._pcf = PCF8574(i2c_port_num, i2c_address)
        self._name = name or DEVICE_DEFAULT_NAME
        self._pin_num = pin_num
        self._invert_logic = invert_logic
        self._unique_id = str(unique_id) + str(pin_num)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return (
            not self._pcf.port[self._pin_num]
            if self._invert_logic
            else self._pcf.port[self._pin_num]
        )

    @property
    def assumed_state(self):
        """Return true if optimistic updates are used."""
        return True

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._pcf.port[self._pin_num] = False if self._invert_logic else True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._pcf.port[self._pin_num] = True if self._invert_logic else False
        self.schedule_update_ha_state()
