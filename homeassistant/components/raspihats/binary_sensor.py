"""Support for raspihats board binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import (
    CONF_ADDRESS, CONF_DEVICE_CLASS, CONF_NAME, DEVICE_DEFAULT_NAME)
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_BOARD, CONF_CHANNELS, CONF_I2C_HATS, CONF_INDEX, CONF_INVERT_LOGIC,
    I2C_HAT_NAMES, I2C_HATS_MANAGER, I2CHatsException)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['raspihats']

DEFAULT_INVERT_LOGIC = False
DEFAULT_DEVICE_CLASS = None

_CHANNELS_SCHEMA = vol.Schema([{
    vol.Required(CONF_INDEX): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): cv.string,
}])

_I2C_HATS_SCHEMA = vol.Schema([{
    vol.Required(CONF_BOARD): vol.In(I2C_HAT_NAMES),
    vol.Required(CONF_ADDRESS): vol.Coerce(int),
    vol.Required(CONF_CHANNELS): _CHANNELS_SCHEMA,
}])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_I2C_HATS): _I2C_HATS_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the raspihats binary_sensor devices."""
    I2CHatBinarySensor.I2C_HATS_MANAGER = hass.data[I2C_HATS_MANAGER]
    binary_sensors = []
    i2c_hat_configs = config.get(CONF_I2C_HATS)
    for i2c_hat_config in i2c_hat_configs:
        address = i2c_hat_config[CONF_ADDRESS]
        board = i2c_hat_config[CONF_BOARD]
        try:
            I2CHatBinarySensor.I2C_HATS_MANAGER.register_board(board, address)
            for channel_config in i2c_hat_config[CONF_CHANNELS]:
                binary_sensors.append(
                    I2CHatBinarySensor(
                        address,
                        channel_config[CONF_INDEX],
                        channel_config[CONF_NAME],
                        channel_config[CONF_INVERT_LOGIC],
                        channel_config[CONF_DEVICE_CLASS]
                    )
                )
        except I2CHatsException as ex:
            _LOGGER.error("Failed to register %s I2CHat@%s %s",
                          board, hex(address), str(ex))
    add_entities(binary_sensors)


class I2CHatBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor that uses a I2C-HAT digital input."""

    I2C_HATS_MANAGER = None

    def __init__(self, address, channel, name, invert_logic, device_class):
        """Initialize the raspihats sensor."""
        self._address = address
        self._channel = channel
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._device_class = device_class
        self._state = self.I2C_HATS_MANAGER.read_di(
            self._address, self._channel)

        def online_callback():
            """Call fired when board is online."""
            self.schedule_update_ha_state()

        self.I2C_HATS_MANAGER.register_online_callback(
            self._address, self._channel, online_callback)

        def edge_callback(state):
            """Read digital input state."""
            self._state = state
            self.schedule_update_ha_state()

        self.I2C_HATS_MANAGER.register_di_callback(
            self._address, self._channel, edge_callback)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of this sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for this sensor."""
        return False

    @property
    def is_on(self):
        """Return the state of this sensor."""
        return self._state != self._invert_logic
