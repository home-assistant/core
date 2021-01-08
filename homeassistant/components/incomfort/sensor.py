"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from homeassistant.const import PRESSURE_BAR, TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN

INTOUCH_HEATER_TEMP = "CV Temp"
INTOUCH_PRESSURE = "CV Pressure"
INTOUCH_TAP_TEMP = "Tap Temp"

INTOUCH_MAP_ATTRS = {
    INTOUCH_HEATER_TEMP: ["heater_temp", "is_pumping"],
    INTOUCH_TAP_TEMP: ["tap_temp", "is_tapping"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an InComfort/InTouch sensor device."""
    client = hass.data[DOMAIN]["client"]
    heater = hass.data[DOMAIN]["heater"]

    async_add_entities(
        [
            IncomfortPressure(client, heater, INTOUCH_PRESSURE),
            IncomfortTemperature(client, heater, INTOUCH_HEATER_TEMP),
            IncomfortTemperature(client, heater, INTOUCH_TAP_TEMP),
        ]
    )


class IncomfortSensor(Entity):
    """Representation of an InComfort/InTouch sensor device."""

    def __init__(self, client, boiler):
        """Initialize the sensor."""
        self._client = client
        self._boiler = boiler

        self._name = None
        self._device_class = None
        self._unit_of_measurement = None

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False


class IncomfortPressure(IncomfortSensor):
    """Representation of an InTouch CV Pressure sensor."""

    def __init__(self, client, boiler, name):
        """Initialize the sensor."""
        super().__init__(client, boiler)

        self._name = name
        self._unit_of_measurement = PRESSURE_BAR

    @property
    def state(self):
        """Return the state/value of the sensor."""
        return self._boiler.status["pressure"]


class IncomfortTemperature(IncomfortSensor):
    """Representation of an InTouch Temperature sensor."""

    def __init__(self, client, boiler, name):
        """Initialize the signal strength sensor."""
        super().__init__(client, boiler)

        self._name = name
        self._device_class = DEVICE_CLASS_TEMPERATURE
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._boiler.status[INTOUCH_MAP_ATTRS[self._name][0]]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        key = INTOUCH_MAP_ATTRS[self._name][1]
        return {key: self._boiler.status[key]}
