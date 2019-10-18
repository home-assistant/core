"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""
from typing import Any, Dict, Optional

from homeassistant.const import (
    PRESSURE_BAR,
    TEMP_CELSIUS,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import DOMAIN

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
    heater = hass.data[DOMAIN]["heater"]

    async_add_entities(
        [
            IncomfortPressure(client, heater, INCOMFORT_PRESSURE),
            IncomfortTemperature(client, heater, INCOMFORT_HEATER_TEMP),
            IncomfortTemperature(client, heater, INCOMFORT_TAP_TEMP),
        ]
    )


class IncomfortSensor(Entity):
    """Representation of an InComfort/InTouch sensor device."""

    def __init__(self, client, heater, name) -> None:
        """Initialize the sensor."""
        self._client = client
        self._heater = heater

        self._unique_id = f"{heater.serial_no}_{slugify(name)}"

        self._name = name
        self._device_class = None
        self._unit_of_measurement = None

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._heater.status[INCOMFORT_MAP_ATTRS[self._name][0]]

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False


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

        self._device_class = DEVICE_CLASS_TEMPERATURE
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the device state attributes."""
        key = INCOMFORT_MAP_ATTRS[self._name][1]
        return {key: self._heater.status[key]}
