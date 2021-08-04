"""Support for switch sensor using I2C PCF8574 chip."""
from pcf8574 import PCF8574

from homeassistant.helpers.entity import ToggleEntity

from .const import (
    CONF_I2C_ADDRESS,
    CONF_I2C_BUS_NUM,
    CONF_INPUT,
    CONF_INVERT_LOGIC,
    CONF_PIN_NAME,
    CONF_PINS,
    DOMAIN,
)


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up switch from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)

    switches = []
    for pin in config[CONF_PINS]:
        if pin[CONF_INPUT]:
            # not handling binary sensor pins here
            continue
        else:
            switches.append(
                PCF8574Switch(
                    config[CONF_I2C_BUS_NUM],
                    config[CONF_I2C_ADDRESS],
                    pin[CONF_PIN_NAME],
                    pin["pin_num"],
                    pin[CONF_INVERT_LOGIC],
                )
            )

    async_add_entities(switches, update_before_add=True)


class PCF8574Switch(ToggleEntity):
    """Representation of a PCF8574 output pin."""

    def __init__(self, i2c_bus_num, i2c_address, name, pin_num, invert_logic):
        """Initialize the pin."""
        self._attr_name = name
        self._attr_unique_id = f"{i2c_bus_num}_{i2c_address}_{pin_num}"
        self._pcf = PCF8574(i2c_bus_num, i2c_address)
        self._pin_num = pin_num
        self._invert_logic = invert_logic

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
