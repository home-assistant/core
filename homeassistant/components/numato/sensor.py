"""Sensor platform integration for ADC ports of Numato USB GPIO expanders.

For more details about this platform, please refer to the documentation at:
https://home-assistant.io/integrations/numato#sensor
"""
import logging

from numato_gpio import NumatoGpioError

import homeassistant.components.numato as numato
from homeassistant.const import CONF_ID, CONF_NAME, CONF_SENSORS
from homeassistant.helpers.entity import Entity

from . import CONF_DST_RANGE, CONF_DST_UNIT, CONF_PORTS, CONF_SRC_RANGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:gauge"


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the configured Numato USB GPIO ADC sensor ports."""
    if discovery_info is None:
        return
    sensors = []
    devices = hass.data[DOMAIN]
    for device in [d for d in devices if CONF_SENSORS in d]:
        device_id = device[CONF_ID]
        ports = device[CONF_SENSORS][CONF_PORTS]
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
