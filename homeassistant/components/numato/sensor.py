"""Sensor platform integration for ADC ports of Numato USB GPIO expanders."""

from __future__ import annotations

import logging

from numato_gpio import NumatoGpioError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ID, CONF_NAME, CONF_SENSORS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_DEVICES,
    CONF_DST_RANGE,
    CONF_DST_UNIT,
    CONF_PORTS,
    CONF_SRC_RANGE,
    DATA_API,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the configured Numato USB GPIO ADC sensor ports."""
    if discovery_info is None:
        return

    api = hass.data[DOMAIN][DATA_API]
    sensors = []
    devices = hass.data[DOMAIN][CONF_DEVICES]
    for device in [d for d in devices if CONF_SENSORS in d]:
        device_id = device[CONF_ID]
        ports = device[CONF_SENSORS][CONF_PORTS]
        for port, adc_def in ports.items():
            try:
                api.setup_input(device_id, port)
            except NumatoGpioError as err:
                _LOGGER.error(
                    "Failed to initialize sensor '%s' on Numato device %s port %s: %s",
                    adc_def[CONF_NAME],
                    device_id,
                    port,
                    err,
                )
                continue
            sensors.append(
                NumatoGpioAdc(
                    adc_def[CONF_NAME],
                    device_id,
                    port,
                    adc_def[CONF_SRC_RANGE],
                    adc_def[CONF_DST_RANGE],
                    adc_def[CONF_DST_UNIT],
                    api,
                )
            )
    add_entities(sensors, True)


class NumatoGpioAdc(SensorEntity):
    """Represents an ADC port of a Numato USB GPIO expander."""

    _attr_icon = "mdi:gauge"

    def __init__(self, name, device_id, port, src_range, dst_range, dst_unit, api):
        """Initialize the sensor."""
        self._name = name
        self._device_id = device_id
        self._port = port
        self._src_range = src_range
        self._dst_range = dst_range
        self._state = None
        self._unit_of_measurement = dst_unit
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest data and updates the state."""
        try:
            adc_val = self._api.read_adc_input(self._device_id, self._port)
            adc_val = self._clamp_to_source_range(adc_val)
            self._state = self._linear_scale_to_dest_range(adc_val)
        except NumatoGpioError as err:
            self._state = None
            _LOGGER.error(
                "Failed to update Numato device %s ADC-port %s: %s",
                self._device_id,
                self._port,
                err,
            )

    def _clamp_to_source_range(self, val):
        # clamp to source range
        val = max(val, self._src_range[0])
        return min(val, self._src_range[1])

    def _linear_scale_to_dest_range(self, val):
        # linear scale to dest range
        src_len = self._src_range[1] - self._src_range[0]
        adc_val_rel = val - self._src_range[0]
        ratio = float(adc_val_rel) / float(src_len)
        dst_len = self._dst_range[1] - self._dst_range[0]
        return self._dst_range[0] + ratio * dst_len
