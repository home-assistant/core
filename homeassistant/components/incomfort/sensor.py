"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""
from typing import Any, Dict, Optional

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
)
from homeassistant.util import slugify

from . import DOMAIN, IncomfortChild

INCOMFORT_HEATER_TEMP = "CV Temp"
INCOMFORT_PRESSURE = "CV Pressure"
INCOMFORT_TAP_TEMP = "Tap Temp"

INCOMFORT_MAP_ATTRS = {
    INCOMFORT_HEATER_TEMP: ["heater_temp", "is_pumping"],
    INCOMFORT_PRESSURE: ["pressure", None],
    INCOMFORT_TAP_TEMP: ["tap_temp", "is_tapping"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an InComfort/InTouch sensor device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    heaters = hass.data[DOMAIN]["heaters"]

    async_add_entities(
        [IncomfortPressure(client, h, INCOMFORT_PRESSURE) for h in heaters]
        + [IncomfortTemperature(client, h, INCOMFORT_HEATER_TEMP) for h in heaters]
        + [IncomfortTemperature(client, h, INCOMFORT_TAP_TEMP) for h in heaters]
    )


class IncomfortSensor(IncomfortChild):
    """Representation of an InComfort/InTouch sensor device."""

    def __init__(self, client, heater, name) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._client = client
        self._heater = heater

        self._unique_id = f"{heater.serial_no}_{slugify(name)}"
        self.entity_id = f"{SENSOR_DOMAIN}.{DOMAIN}_{slugify(name)}"
        self._name = f"Boiler {name}"

        self._device_class = None
        self._state_attr = INCOMFORT_MAP_ATTRS[name][0]
        self._unit_of_measurement = None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._heater.status[self._state_attr]

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement


class IncomfortPressure(IncomfortSensor):
    """Representation of an InTouch CV Pressure sensor."""

    def __init__(self, client, heater, name) -> None:
        """Initialize the sensor."""
        super().__init__(client, heater, name)

        self._device_class = DEVICE_CLASS_PRESSURE
        self._unit_of_measurement = PRESSURE_BAR


class IncomfortTemperature(IncomfortSensor):
    """Representation of an InTouch Temperature sensor."""

    def __init__(self, client, heater, name) -> None:
        """Initialize the signal strength sensor."""
        super().__init__(client, heater, name)

        self._attr = INCOMFORT_MAP_ATTRS[name][1]
        self._device_class = DEVICE_CLASS_TEMPERATURE
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the device state attributes."""
        return {self._attr: self._heater.status[self._attr]}
