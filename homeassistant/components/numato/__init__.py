"""Support for controlling GPIO pins of a Numato Labs USB GPIO expander."""
import logging

import numato_gpio as gpio
import voluptuous as vol

from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_SWITCHES,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "numato"

CONF_INVERT_LOGIC = "invert_logic"
CONF_DISCOVER = "discover"
CONF_DEVICES = "devices"
CONF_DEVICE_ID = "id"
CONF_PORTS = "ports"
CONF_SRC_RANGE = "source_range"
CONF_DST_RANGE = "destination_range"
CONF_DST_UNIT = "unit"
DEFAULT_INVERT_LOGIC = False
DEFAULT_SRC_RANGE = [0, 1024]
DEFAULT_DST_RANGE = [0.0, 100.0]
DEFAULT_DEV = [f"/dev/ttyACM{i}" for i in range(10)]

PORT_RANGE = range(1, 8)  # ports 0-7 are ADC capable

DATA_PORTS_IN_USE = "ports_in_use"
DATA_API = "api"


def int_range(rng):
    """Validate the input array to describe a range by two integers."""
    if not (isinstance(rng[0], int) and isinstance(rng[1], int)):
        raise vol.Invalid(f"Only integers are allowed: {rng}")
    if len(rng) != 2:
        raise vol.Invalid(f"Only two numbers allowed in a range: {rng}")
    if rng[0] > rng[1]:
        raise vol.Invalid(f"Lower range bound must come first: {rng}")
    return rng


def float_range(rng):
    """Validate the input array to describe a range by two floats."""
    try:
        coe = vol.Coerce(float)
        coe(rng[0])
        coe(rng[1])
    except vol.CoerceInvalid as err:
        raise vol.Invalid(f"Only int or float values are allowed: {rng}") from err
    if len(rng) != 2:
        raise vol.Invalid(f"Only two numbers allowed in a range: {rng}")
    if rng[0] > rng[1]:
        raise vol.Invalid(f"Lower range bound must come first: {rng}")
    return rng


def adc_port_number(num):
    """Validate input number to be in the range of ADC enabled ports."""
    try:
        num = int(num)
    except ValueError as err:
        raise vol.Invalid(f"Port numbers must be integers: {num}") from err
    if num not in range(1, 8):
        raise vol.Invalid(f"Only port numbers from 1 to 7 are ADC capable: {num}")
    return num


ADC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SRC_RANGE, default=DEFAULT_SRC_RANGE): int_range,
        vol.Optional(CONF_DST_RANGE, default=DEFAULT_DST_RANGE): float_range,
        vol.Optional(CONF_DST_UNIT, default=PERCENTAGE): cv.string,
    }
)

PORTS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

IO_PORTS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORTS): PORTS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        CONF_BINARY_SENSORS: IO_PORTS_SCHEMA,
        CONF_SWITCHES: IO_PORTS_SCHEMA,
        CONF_SENSORS: {CONF_PORTS: {adc_port_number: ADC_SCHEMA}},
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            CONF_DEVICES: vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            vol.Optional(CONF_DISCOVER, default=DEFAULT_DEV): vol.All(
                cv.ensure_list, [cv.string]
            ),
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the numato integration.

    Discovers available Numato devices and loads the binary_sensor, sensor and
    switch platforms.

    Returns False on error during device discovery (e.g. duplicate ID),
    otherwise returns True.

    No exceptions should occur, since the platforms are initialized on a best
    effort basis, which means, errors are handled locally.
    """
    hass.data[DOMAIN] = config[DOMAIN]

    try:
        gpio.discover(config[DOMAIN][CONF_DISCOVER])
    except gpio.NumatoGpioError as err:
        _LOGGER.info("Error discovering Numato devices: %s", err)
        gpio.cleanup()
        return False

    _LOGGER.info(
        "Initializing Numato 32 port USB GPIO expanders with IDs: %s",
        ", ".join(str(d) for d in gpio.devices),
    )

    hass.data[DOMAIN][DATA_API] = NumatoAPI()

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        _LOGGER.debug("Clean up Numato GPIO")
        gpio.cleanup()
        if DATA_API in hass.data[DOMAIN]:
            hass.data[DOMAIN][DATA_API].ports_registered.clear()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        _LOGGER.debug("Setup cleanup at stop for Numato GPIO")
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)

    load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
    load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    load_platform(hass, Platform.SWITCH, DOMAIN, {}, config)
    return True


class NumatoAPI:
    """Home-Assistant specific API for numato device access."""

    def __init__(self):
        """Initialize API state."""
        self.ports_registered = {}

    def check_port_free(self, device_id, port, direction):
        """Check whether a port is still free set up.

        Fail with exception if it has already been registered.
        """
        if (device_id, port) not in self.ports_registered:
            self.ports_registered[(device_id, port)] = direction
        else:
            raise gpio.NumatoGpioError(
                "Device {} port {} already in use as {}.".format(
                    device_id,
                    port,
                    "input"
                    if self.ports_registered[(device_id, port)] == gpio.IN
                    else "output",
                )
            )

    def check_device_id(self, device_id):
        """Check whether a device has been discovered.

        Fail with exception.
        """
        if device_id not in gpio.devices:
            raise gpio.NumatoGpioError(f"Device {device_id} not available.")

    def check_port(self, device_id, port, direction):
        """Raise an error if the port setup doesn't match the direction."""
        self.check_device_id(device_id)
        if (device_id, port) not in self.ports_registered:
            raise gpio.NumatoGpioError(
                f"Port {port} is not set up for numato device {device_id}."
            )
        msg = {
            gpio.OUT: (
                f"Trying to write to device {device_id} port {port} set up as input."
            ),
            gpio.IN: (
                f"Trying to read from device {device_id} port {port} set up as output."
            ),
        }
        if self.ports_registered[(device_id, port)] != direction:
            raise gpio.NumatoGpioError(msg[direction])

    def setup_output(self, device_id, port):
        """Set up a GPIO as output."""
        self.check_device_id(device_id)
        self.check_port_free(device_id, port, gpio.OUT)
        gpio.devices[device_id].setup(port, gpio.OUT)

    def setup_input(self, device_id, port):
        """Set up a GPIO as input."""
        self.check_device_id(device_id)
        gpio.devices[device_id].setup(port, gpio.IN)
        self.check_port_free(device_id, port, gpio.IN)

    def write_output(self, device_id, port, value):
        """Write a value to a GPIO."""
        self.check_port(device_id, port, gpio.OUT)
        gpio.devices[device_id].write(port, value)

    def read_input(self, device_id, port):
        """Read a value from a GPIO."""
        self.check_port(device_id, port, gpio.IN)
        return gpio.devices[device_id].read(port)

    def read_adc_input(self, device_id, port):
        """Read an ADC value from a GPIO ADC port."""
        self.check_port(device_id, port, gpio.IN)
        self.check_device_id(device_id)
        return gpio.devices[device_id].adc_read(port)

    def edge_detect(self, device_id, port, event_callback):
        """Add detection for RISING and FALLING events."""
        self.check_port(device_id, port, gpio.IN)
        gpio.devices[device_id].add_event_detect(port, event_callback, gpio.BOTH)
        gpio.devices[device_id].notify = True
