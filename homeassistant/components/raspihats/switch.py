"""Support for raspihats board switches."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_ADDRESS, CONF_NAME, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

from . import (
    CONF_BOARD,
    CONF_CHANNELS,
    CONF_I2C_HATS,
    CONF_INDEX,
    CONF_INITIAL_STATE,
    CONF_INVERT_LOGIC,
    I2C_HAT_NAMES,
    I2C_HATS_MANAGER,
    I2CHatsException,
)

_LOGGER = logging.getLogger(__name__)

_CHANNELS_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_INDEX): cv.positive_int,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_INVERT_LOGIC, default=False): cv.boolean,
            vol.Optional(CONF_INITIAL_STATE): cv.boolean,
        }
    ]
)

_I2C_HATS_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_BOARD): vol.In(I2C_HAT_NAMES),
            vol.Required(CONF_ADDRESS): vol.Coerce(int),
            vol.Required(CONF_CHANNELS): _CHANNELS_SCHEMA,
        }
    ]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_I2C_HATS): _I2C_HATS_SCHEMA}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the raspihats switch devices."""
    I2CHatSwitch.I2C_HATS_MANAGER = hass.data[I2C_HATS_MANAGER]
    switches = []
    i2c_hat_configs = config.get(CONF_I2C_HATS)
    for i2c_hat_config in i2c_hat_configs:
        board = i2c_hat_config[CONF_BOARD]
        address = i2c_hat_config[CONF_ADDRESS]
        try:
            I2CHatSwitch.I2C_HATS_MANAGER.register_board(board, address)
            for channel_config in i2c_hat_config[CONF_CHANNELS]:
                switches.append(
                    I2CHatSwitch(
                        board,
                        address,
                        channel_config[CONF_INDEX],
                        channel_config[CONF_NAME],
                        channel_config[CONF_INVERT_LOGIC],
                        channel_config.get(CONF_INITIAL_STATE),
                    )
                )
        except I2CHatsException as ex:
            _LOGGER.error(
                "Failed to register %s I2CHat@%s %s", board, hex(address), str(ex)
            )
    add_entities(switches)


class I2CHatSwitch(ToggleEntity):
    """Representation  a switch that uses a I2C-HAT digital output."""

    I2C_HATS_MANAGER = None

    def __init__(self, board, address, channel, name, invert_logic, initial_state):
        """Initialize switch."""
        self._board = board
        self._address = address
        self._channel = channel
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        if initial_state is not None:
            if self._invert_logic:
                state = not initial_state
            else:
                state = initial_state
            self.I2C_HATS_MANAGER.write_dq(self._address, self._channel, state)

        def online_callback():
            """Call fired when board is online."""
            self.schedule_update_ha_state()

        self.I2C_HATS_MANAGER.register_online_callback(
            self._address, self._channel, online_callback
        )

    def _log_message(self, message):
        """Create log message."""
        string = self._name + " "
        string += f"{self._board}I2CHat@{hex(self._address)} "
        string += f"channel:{str(self._channel)}{message}"
        return string

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        try:
            state = self.I2C_HATS_MANAGER.read_dq(self._address, self._channel)
            return state != self._invert_logic
        except I2CHatsException as ex:
            _LOGGER.error(self._log_message(f"Is ON check failed, {ex!s}"))
            return False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            state = self._invert_logic is False
            self.I2C_HATS_MANAGER.write_dq(self._address, self._channel, state)
            self.schedule_update_ha_state()
        except I2CHatsException as ex:
            _LOGGER.error(self._log_message(f"Turn ON failed, {ex!s}"))

    def turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            state = self._invert_logic is not False
            self.I2C_HATS_MANAGER.write_dq(self._address, self._channel, state)
            self.schedule_update_ha_state()
        except I2CHatsException as ex:
            _LOGGER.error(self._log_message(f"Turn OFF failed, {ex!s}"))
