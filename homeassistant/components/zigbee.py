"""
Support for ZigBee devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zigbee/
"""
import logging
from binascii import hexlify, unhexlify

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import JobPriority
from homeassistant.helpers.entity import Entity

DOMAIN = "zigbee"
REQUIREMENTS = ("xbee-helper==0.0.6",)

CONF_DEVICE = "device"
CONF_BAUD = "baud"

DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD = 9600
DEFAULT_ADC_MAX_VOLTS = 1.2

# Copied from xbee_helper during setup()
GPIO_DIGITAL_OUTPUT_LOW = None
GPIO_DIGITAL_OUTPUT_HIGH = None
ADC_PERCENTAGE = None
ZIGBEE_EXCEPTION = None
ZIGBEE_TX_FAILURE = None

DEVICE = None

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the connection to the ZigBee device."""
    global DEVICE
    global GPIO_DIGITAL_OUTPUT_LOW
    global GPIO_DIGITAL_OUTPUT_HIGH
    global ADC_PERCENTAGE
    global ZIGBEE_EXCEPTION
    global ZIGBEE_TX_FAILURE

    import xbee_helper.const as xb_const
    from xbee_helper import ZigBee
    from xbee_helper.exceptions import ZigBeeException, ZigBeeTxFailure
    from serial import Serial, SerialException

    GPIO_DIGITAL_OUTPUT_LOW = xb_const.GPIO_DIGITAL_OUTPUT_LOW
    GPIO_DIGITAL_OUTPUT_HIGH = xb_const.GPIO_DIGITAL_OUTPUT_HIGH
    ADC_PERCENTAGE = xb_const.ADC_PERCENTAGE
    ZIGBEE_EXCEPTION = ZigBeeException
    ZIGBEE_TX_FAILURE = ZigBeeTxFailure

    usb_device = config[DOMAIN].get(CONF_DEVICE, DEFAULT_DEVICE)
    baud = int(config[DOMAIN].get(CONF_BAUD, DEFAULT_BAUD))
    try:
        ser = Serial(usb_device, baud)
    except SerialException as exc:
        _LOGGER.exception("Unable to open serial port for ZigBee: %s", exc)
        return False
    DEVICE = ZigBee(ser)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_serial_port)
    return True


def close_serial_port(*args):
    """Close the serial port we're using to communicate with the ZigBee."""
    DEVICE.zb.serial.close()


class ZigBeeConfig(object):
    """Handle the fetching of configuration from the config file."""

    def __init__(self, config):
        """Initialize the configuration."""
        self._config = config
        self._should_poll = config.get("poll", True)

    @property
    def name(self):
        """The name given to the entity."""
        return self._config["name"]

    @property
    def address(self):
        """The address of the device.

        If an address has been provided, unhexlify it, otherwise return None
        as we're talking to our local ZigBee device.
        """
        address = self._config.get("address")
        if address is not None:
            address = unhexlify(address)
        return address

    @property
    def should_poll(self):
        """No polling needed."""
        return self._should_poll


class ZigBeePinConfig(ZigBeeConfig):
    """Handle the fetching of configuration from the config file."""

    @property
    def pin(self):
        """The GPIO pin number."""
        return self._config["pin"]


class ZigBeeDigitalPinConfig(ZigBeePinConfig):
    """Handle the fetching of configuration from the config file."""

    def __init__(self, config):
        """Initialize the configuration."""
        super(ZigBeeDigitalPinConfig, self).__init__(config)
        self._bool2state, self._state2bool = self.boolean_maps

    @property
    def boolean_maps(self):
        """Create dicts to map booleans to pin high/low and vice versa.

        Depends on the config item "on_state" which should be set to "low"
        or "high".
        """
        if self._config.get("on_state", "").lower() == "low":
            bool2state = {
                True: GPIO_DIGITAL_OUTPUT_LOW,
                False: GPIO_DIGITAL_OUTPUT_HIGH
            }
        else:
            bool2state = {
                True: GPIO_DIGITAL_OUTPUT_HIGH,
                False: GPIO_DIGITAL_OUTPUT_LOW
            }
        state2bool = {v: k for k, v in bool2state.items()}
        return bool2state, state2bool

    @property
    def bool2state(self):
        """A dictionary mapping booleans to GPIOSetting objects.

        For the translation of on/off as being pin high or low.
        """
        return self._bool2state

    @property
    def state2bool(self):
        """A dictionary mapping GPIOSetting objects to booleans.

        For the translation of pin high/low as being on or off.
        """
        return self._state2bool

# Create an alias so that ZigBeeDigitalOutConfig has a logical opposite.
ZigBeeDigitalInConfig = ZigBeeDigitalPinConfig


class ZigBeeDigitalOutConfig(ZigBeeDigitalPinConfig):
    """A subclass of ZigBeeDigitalPinConfig.

    Set _should_poll to default as False instead of True. The value will
    still be overridden by the presence of a 'poll' config entry.
    """

    def __init__(self, config):
        """Initialize the ZigBee Digital out."""
        super(ZigBeeDigitalOutConfig, self).__init__(config)
        self._should_poll = config.get("poll", False)


class ZigBeeAnalogInConfig(ZigBeePinConfig):
    """Representation of a ZigBee GPIO pin set to analog in."""

    @property
    def max_voltage(self):
        """The voltage at which the ADC will report its highest value."""
        return float(self._config.get("max_volts", DEFAULT_ADC_MAX_VOLTS))


class ZigBeeDigitalIn(Entity):
    """Representation of a GPIO pin configured as a digital input."""

    def __init__(self, hass, config):
        """Initialize the device."""
        self._config = config
        self._state = False
        # Get initial state
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

    @property
    def name(self):
        """Return the name of the input."""
        return self._config.name

    @property
    def should_poll(self):
        """Return the state of the polling, if needed."""
        return self._config.should_poll

    @property
    def is_on(self):
        """Return True if the Entity is on, else False."""
        return self._state

    def update(self):
        """Ask the ZigBee device what its output is set to."""
        try:
            pin_state = DEVICE.get_gpio_pin(
                self._config.pin,
                self._config.address)
        except ZIGBEE_TX_FAILURE:
            _LOGGER.warning(
                "Transmission failure when attempting to get sample from "
                "ZigBee device at address: %s", hexlify(self._config.address))
            return
        except ZIGBEE_EXCEPTION as exc:
            _LOGGER.exception(
                "Unable to get sample from ZigBee device: %s", exc)
            return
        self._state = self._config.state2bool[pin_state]


class ZigBeeDigitalOut(ZigBeeDigitalIn):
    """Representation of a GPIO pin configured as a digital input."""

    def _set_state(self, state):
        """Initialize the ZigBee digital out device."""
        try:
            DEVICE.set_gpio_pin(
                self._config.pin,
                self._config.bool2state[state],
                self._config.address)
        except ZIGBEE_TX_FAILURE:
            _LOGGER.warning(
                "Transmission failure when attempting to set output pin on "
                "ZigBee device at address: %s", hexlify(self._config.address))
            return
        except ZIGBEE_EXCEPTION as exc:
            _LOGGER.exception(
                "Unable to set digital pin on ZigBee device: %s", exc)
            return
        self._state = state
        if not self.should_poll:
            self.update_ha_state()

    def turn_on(self, **kwargs):
        """Set the digital output to its 'on' state."""
        self._set_state(True)

    def turn_off(self, **kwargs):
        """Set the digital output to its 'off' state."""
        self._set_state(False)


class ZigBeeAnalogIn(Entity):
    """Representation of a GPIO pin configured as an analog input."""

    def __init__(self, hass, config):
        """Initialize the ZigBee analog in device."""
        self._config = config
        self._value = None
        # Get initial state
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

    @property
    def name(self):
        """The name of the input."""
        return self._config.name

    @property
    def should_poll(self):
        """The state of the polling, if needed."""
        return self._config.should_poll

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "%"

    def update(self):
        """Get the latest reading from the ADC."""
        try:
            self._value = DEVICE.read_analog_pin(
                self._config.pin,
                self._config.max_voltage,
                self._config.address,
                ADC_PERCENTAGE)
        except ZIGBEE_TX_FAILURE:
            _LOGGER.warning(
                "Transmission failure when attempting to get sample from "
                "ZigBee device at address: %s", hexlify(self._config.address))
        except ZIGBEE_EXCEPTION as exc:
            _LOGGER.exception(
                "Unable to get sample from ZigBee device: %s", exc)
