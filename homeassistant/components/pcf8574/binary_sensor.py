"""Support for switch sensor using I2C PCF8574 chip."""
from pcf8574 import PCF8574

from homeassistant.components.binary_sensor import BinarySensorEntity

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
    """Set up binary_sensor from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)

    binary_sensors = []
    for pin in config[CONF_PINS]:
        if pin[CONF_INPUT]:
            binary_sensors.append(
                PCF8574BinarySensor(
                    config[CONF_I2C_BUS_NUM],
                    config[CONF_I2C_ADDRESS],
                    pin[CONF_PIN_NAME],
                    pin["pin_num"],
                    pin[CONF_INVERT_LOGIC],
                )
            )
        else:
            # not handling switch pins here
            continue

    async_add_entities(binary_sensors, update_before_add=True)


class PCF8574BinarySensor(BinarySensorEntity):
    """Representation of a PCF8574 input pin."""

    def __init__(self, i2c_bus_num, i2c_address, name, pin_num, invert_logic):
        """Initialize the pin."""
        self._attr_name = name
        self._attr_unique_id = f"{i2c_bus_num}_{i2c_address}_{pin_num}"
        self._attr_is_on = None
        self._pcf = PCF8574(i2c_bus_num, i2c_address)  # TODO
        self._pin_num = pin_num
        self._invert_logic = invert_logic

    async def async_update(self):
        """Get the latest data from the PCF8574 and updates the state."""
        self._attr_is_on = self._pcf.port[self._pin_num] != self._invert_logic
