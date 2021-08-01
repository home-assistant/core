"""Support for switch sensor using I2C PCF8574 chip."""
from pcf8574 import PCF8574

from homeassistant.helpers.entity import ToggleEntity

from .const import CONF_I2C_ADDRESS, CONF_I2C_PORT_NUM, CONF_INVERT_LOGIC, DOMAIN


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

    invert_logic = config[CONF_INVERT_LOGIC]
    switches = []
    for i in range(8):
        # try to get all switch names. if key exist also the switch exists
        switch_name = config.get(f"switch_{i+1}_name")
        if switch_name is not None:
            switches.append(
                PCF8574Switch(
                    config[CONF_I2C_PORT_NUM],
                    config[CONF_I2C_ADDRESS],
                    switch_name,
                    i,
                    invert_logic,
                    config_entry.entry_id,
                )
            )
    async_add_entities(switches, update_before_add=True)


class PCF8574Switch(ToggleEntity):
    """Representation of a PCF8574 output pin."""

    def __init__(
        self, i2c_port_num, i2c_address, name, pin_num, invert_logic, entry_id
    ):
        """Initialize the pin."""
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{pin_num}"
        self._pcf = PCF8574(i2c_port_num, i2c_address)
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
