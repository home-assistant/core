"""Sensor platform integration for ADC ports of Numato USB GPIO expanders.

For more details about this platform, please refer to the documentation at:
https://home-assistant.io/integrations/numato#sensor
"""
import logging

from numato_gpio import NumatoGpioError
import voluptuous as vol

import homeassistant.components.numato as numato
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ["numato"]

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Numato GPIO ADC"
CONF_DEVICES = "devices"
CONF_PORTS = "ports"
DEFAULT_SRC_RANGE = [0, 1024]
DEFAULT_DST_RANGE = [0.0, 100.0]
DEFAULT_UNIT = "%"
CONF_SRC_RANGE = "source_range"
CONF_DST_RANGE = "destination_range"
CONF_DST_UNIT = "unit"
ICON = "mdi:gauge"
PORT_RANGE = range(1, 8)  # ports 0-7 are adc capable


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
    except vol.CoerceInvalid:
        raise vol.Invalid(f"Only int or float values are allowed: {rng}")
    if len(rng) != 2:
        raise vol.Invalid(f"Only two numbers allowed in a range: {rng}")
    if rng[0] > rng[1]:
        raise vol.Invalid(f"Lower range bound must come first: {rng}")
    return rng


def adc_port_number(num):
    """Validate input number to be in the range of ADC enabled ports."""
    try:
        num = int(num)
    except (ValueError):
        raise vol.Invalid(f"Port numbers must be integers: {num}")
    if num not in range(1, 8):
        raise vol.Invalid(f"Only port numbers from 1 to 7 are ADC capable: {num}")
    return num


_ADC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SRC_RANGE, default=DEFAULT_SRC_RANGE): int_range,
        vol.Optional(CONF_DST_RANGE, default=DEFAULT_DST_RANGE): float_range,
        vol.Optional(CONF_DST_UNIT, default=DEFAULT_UNIT): cv.string,
    }
)

_PORTS_SCHEMA = vol.Schema({adc_port_number: _ADC_SCHEMA})
_DEVICE_SCHEMA = vol.Schema(
    {vol.Required(CONF_ID): cv.positive_int, vol.Required(CONF_PORTS): _PORTS_SCHEMA}
)
_DEVICES_SCHEMA = vol.All(list, [_DEVICE_SCHEMA])
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_DEVICES): _DEVICES_SCHEMA})


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the configured Numato USB GPIO ADC sensor ports."""
    sensors = []
    devices = config.get(CONF_DEVICES)
    for device in devices:
        device_id = device[CONF_ID]
        ports = device[CONF_PORTS]
        for port_id, adc_def in ports.items():
            try:
                sensors.append(
                    NumatoGpioAdc(
                        adc_def[CONF_NAME],
                        device_id,
                        port_id,
                        adc_def[CONF_SRC_RANGE],
                        adc_def[CONF_DST_RANGE],
                        adc_def[CONF_DST_UNIT],
                    )
                )
            except NumatoGpioError as err:
                _LOGGER.error(
                    "Failed to initialize Numato device %s port %s: %s",
                    device_id,
                    port_id,
                    str(err),
                )
    add_devices(sensors, True)


class NumatoGpioAdc(Entity):
    """Represents an ADC port of a Numato USB GPIO expander."""

    def __init__(self, name, device_id, port, src_range, dst_range, dst_unit):
        """Initialize the sensor."""
        self._name = name
        self._device_id = device_id
        self._port = port
        self._src_range = src_range
        self._dst_range = dst_range
        self._state = None
        self._unit_of_measurement = dst_unit
        numato.setup_input(self._device_id, self._port)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the state."""
        try:
            adc_val = numato.read_adc_input(self._device_id, self._port)
            # clamp to source range
            adc_val = max(adc_val, self._src_range[0])
            adc_val = min(adc_val, self._src_range[1])
            # linear scale to dest range
            src_len = self._src_range[1] - self._src_range[0]
            adc_val_rel = adc_val - self._src_range[0]
            ratio = float(adc_val_rel) / float(src_len)
            dst_len = self._dst_range[1] - self._dst_range[0]
            dest_val = self._dst_range[0] + ratio * dst_len
            self._state = dest_val
        except NumatoGpioError as err:
            self._state = None
            _LOGGER.error(
                "Failed to update Numato device %s ADC-port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
