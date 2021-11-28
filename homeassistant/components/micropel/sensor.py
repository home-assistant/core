"""Support for Micropel Word sensors."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from . import SENSOR_SCHEMA
from .const import (
    CONF_DATA_TYPE,
    CONF_HUB,
    CONF_PLC,
    CONF_PRECISION,
    CONF_REGISTER_TYPE,
    CONF_SCALE,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DOMAIN,
    REGISTER_TYPE_WORD,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Micropel sensors."""
    sensors = []

    for sensor in config[CONF_SENSORS]:
        hub_name = sensor[CONF_HUB]
        hub = hass.data[DOMAIN][hub_name]
        sensors.append(
            MicropelRegisterSensor(
                hub,
                sensor[CONF_UNIQUE_ID],
                sensor[CONF_NAME],
                sensor.get(CONF_PLC),
                sensor[CONF_ADDRESS],
                sensor[CONF_REGISTER_TYPE],
                sensor.get(CONF_UNIT_OF_MEASUREMENT),
                sensor[CONF_SCALE],
                sensor[CONF_OFFSET],
                sensor[CONF_PRECISION],
                sensor[CONF_DATA_TYPE],
                sensor.get(CONF_DEVICE_CLASS),
            )
        )

    if not sensors:
        return False
    add_entities(sensors)


class MicropelRegisterSensor(RestoreEntity, SensorEntity):
    """Micropel sensor."""

    def __init__(
        self,
        hub,
        unique_id,
        name,
        plc,
        address,
        register_type,
        unit_of_measurement,
        scale,
        offset,
        precision,
        data_type,
        device_class,
    ):
        """Initialize the modbus register sensor."""
        self._hub = hub
        self._unique_id = unique_id
        self._name = name
        self._plc = int(plc)
        self._address = int(address)
        self._register_type = register_type
        self._unit_of_measurement = unit_of_measurement
        self._scale = scale
        self._offset = float(offset)
        self._precision = precision
        self._data_type = data_type
        self._device_class = device_class
        self._value = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._value = state.state

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._unit_of_measurement == "F" or self._unit_of_measurement == "°F":
            return TEMP_FAHRENHEIT
        if self._unit_of_measurement == "K" or self._unit_of_measurement == "°K":
            return TEMP_KELVIN
        if self._unit_of_measurement == "C" or self._unit_of_measurement == "°C":
            return TEMP_CELSIUS
        return self._unit_of_measurement

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return self._unique_id

    def update(self):
        """Update the state of the sensor."""
        try:
            if self._register_type == REGISTER_TYPE_WORD:
                result = self._hub.read_word(self._plc, self._address)
        except Exception:
            self._available = False
            return

        if self._data_type == DATA_TYPE_INT:
            self._value = round((int(result, 0) * self._scale) + self._offset)
        elif self._data_type == DATA_TYPE_FLOAT:
            val = (int(result, 0) * self._scale) + self._offset
            self._value = f"{float(val):.{self._precision}f}"

        self._available = True
