"""Support for controlling raspihats boards."""
import logging
import threading
import time

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'raspihats'

CONF_I2C_HATS = 'i2c_hats'
CONF_BOARD = 'board'
CONF_CHANNELS = 'channels'
CONF_INDEX = 'index'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_INITIAL_STATE = 'initial_state'

I2C_HAT_NAMES = [
    'Di16', 'Rly10', 'Di6Rly6',
    'DI16ac', 'DQ10rly', 'DQ16oc', 'DI6acDQ6rly'
]

I2C_HATS_MANAGER = 'I2CH_MNG'


def setup(hass, config):
    """Set up the raspihats component."""
    hass.data[I2C_HATS_MANAGER] = I2CHatsManager()

    def start_i2c_hats_keep_alive(event):
        """Start I2C-HATs keep alive."""
        hass.data[I2C_HATS_MANAGER].start_keep_alive()

    def stop_i2c_hats_keep_alive(event):
        """Stop I2C-HATs keep alive."""
        hass.data[I2C_HATS_MANAGER].stop_keep_alive()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_i2c_hats_keep_alive)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_i2c_hats_keep_alive)
    return True


def log_message(source, *parts):
    """Build log message."""
    message = source.__class__.__name__
    for part in parts:
        message += ": " + str(part)
    return message


class I2CHatsException(Exception):
    """I2C-HATs exception."""


class I2CHatsDIScanner:
    """Scan Digital Inputs and fire callbacks."""

    _DIGITAL_INPUTS = "di"
    _OLD_VALUE = "old_value"
    _CALLBACKS = "callbacks"

    def setup(self, i2c_hat):
        """Set up the I2C-HAT instance for digital inputs scanner."""
        if hasattr(i2c_hat, self._DIGITAL_INPUTS):
            digital_inputs = getattr(i2c_hat, self._DIGITAL_INPUTS)
            old_value = None
            # Add old value attribute
            setattr(digital_inputs, self._OLD_VALUE, old_value)
            # Add callbacks dict attribute {channel: callback}
            setattr(digital_inputs, self._CALLBACKS, {})

    def register_callback(self, i2c_hat, channel, callback):
        """Register edge callback."""
        if hasattr(i2c_hat, self._DIGITAL_INPUTS):
            digital_inputs = getattr(i2c_hat, self._DIGITAL_INPUTS)
            callbacks = getattr(digital_inputs, self._CALLBACKS)
            callbacks[channel] = callback
            setattr(digital_inputs, self._CALLBACKS, callbacks)

    def scan(self, i2c_hat):
        """Scan I2C-HATs digital inputs and fire callbacks."""
        if hasattr(i2c_hat, self._DIGITAL_INPUTS):
            digital_inputs = getattr(i2c_hat, self._DIGITAL_INPUTS)
            callbacks = getattr(digital_inputs, self._CALLBACKS)
            old_value = getattr(digital_inputs, self._OLD_VALUE)
            value = digital_inputs.value    # i2c data transfer
            if old_value is not None and value != old_value:
                for channel in range(0, len(digital_inputs.channels)):
                    state = (value >> channel) & 0x01
                    old_state = (old_value >> channel) & 0x01
                    if state != old_state:
                        callback = callbacks.get(channel, None)
                        if callback is not None:
                            callback(state)
            setattr(digital_inputs, self._OLD_VALUE, value)


class I2CHatsManager(threading.Thread):
    """Manages all I2C-HATs instances."""

    _EXCEPTION = "exception"
    _CALLBACKS = "callbacks"

    def __init__(self):
        """Init I2C-HATs Manager."""
        threading.Thread.__init__(self)
        self._lock = threading.Lock()
        self._i2c_hats = {}
        self._run = False
        self._di_scanner = I2CHatsDIScanner()

    def register_board(self, board, address):
        """Register I2C-HAT."""
        with self._lock:
            i2c_hat = self._i2c_hats.get(address)
            if i2c_hat is None:
                # pylint: disable=import-error,no-name-in-module
                import raspihats.i2c_hats as module
                constructor = getattr(module, board)
                i2c_hat = constructor(address)
                setattr(i2c_hat, self._CALLBACKS, {})

                # Setting exception attribute will trigger online callbacks
                # when keep alive thread starts.
                setattr(i2c_hat, self._EXCEPTION, None)

                self._di_scanner.setup(i2c_hat)
                self._i2c_hats[address] = i2c_hat
                status_word = i2c_hat.status  # read status_word to reset bits
                _LOGGER.info(
                    log_message(self, i2c_hat, "registered", status_word))

    def run(self):
        """Keep alive for I2C-HATs."""
        # pylint: disable=import-error,no-name-in-module
        from raspihats.i2c_hats import ResponseException

        _LOGGER.info(log_message(self, "starting"))

        while self._run:
            with self._lock:
                for i2c_hat in list(self._i2c_hats.values()):
                    try:
                        self._di_scanner.scan(i2c_hat)
                        self._read_status(i2c_hat)

                        if hasattr(i2c_hat, self._EXCEPTION):
                            if getattr(i2c_hat, self._EXCEPTION) is not None:
                                _LOGGER.warning(
                                    log_message(self, i2c_hat, "online again")
                                )
                            delattr(i2c_hat, self._EXCEPTION)
                            # trigger online callbacks
                            callbacks = getattr(i2c_hat, self._CALLBACKS)
                            for callback in list(callbacks.values()):
                                callback()
                    except ResponseException as ex:
                        if not hasattr(i2c_hat, self._EXCEPTION):
                            _LOGGER.error(
                                log_message(self, i2c_hat, ex)
                            )
                        setattr(i2c_hat, self._EXCEPTION, ex)
            time.sleep(0.05)
        _LOGGER.info(log_message(self, "exiting"))

    def _read_status(self, i2c_hat):
        """Read I2C-HATs status."""
        status_word = i2c_hat.status
        if status_word.value != 0x00:
            _LOGGER.error(log_message(self, i2c_hat, status_word))

    def start_keep_alive(self):
        """Start keep alive mechanism."""
        self._run = True
        threading.Thread.start(self)

    def stop_keep_alive(self):
        """Stop keep alive mechanism."""
        self._run = False
        self.join()

    def register_di_callback(self, address, channel, callback):
        """Register I2C-HAT digital input edge callback."""
        with self._lock:
            i2c_hat = self._i2c_hats[address]
            self._di_scanner.register_callback(i2c_hat, channel, callback)

    def register_online_callback(self, address, channel, callback):
        """Register I2C-HAT online callback."""
        with self._lock:
            i2c_hat = self._i2c_hats[address]
            callbacks = getattr(i2c_hat, self._CALLBACKS)
            callbacks[channel] = callback
            setattr(i2c_hat, self._CALLBACKS, callbacks)

    def read_di(self, address, channel):
        """Read a value from a I2C-HAT digital input."""
        # pylint: disable=import-error,no-name-in-module
        from raspihats.i2c_hats import ResponseException

        with self._lock:
            i2c_hat = self._i2c_hats[address]
            try:
                value = i2c_hat.di.value
                return (value >> channel) & 0x01
            except ResponseException as ex:
                raise I2CHatsException(str(ex))

    def write_dq(self, address, channel, value):
        """Write a value to a I2C-HAT digital output."""
        # pylint: disable=import-error,no-name-in-module
        from raspihats.i2c_hats import ResponseException

        with self._lock:
            i2c_hat = self._i2c_hats[address]
            try:
                i2c_hat.dq.channels[channel] = value
            except ResponseException as ex:
                raise I2CHatsException(str(ex))

    def read_dq(self, address, channel):
        """Read a value from a I2C-HAT digital output."""
        # pylint: disable=import-error,no-name-in-module
        from raspihats.i2c_hats import ResponseException

        with self._lock:
            i2c_hat = self._i2c_hats[address]
            try:
                return i2c_hat.dq.channels[channel]
            except ResponseException as ex:
                raise I2CHatsException(str(ex))
