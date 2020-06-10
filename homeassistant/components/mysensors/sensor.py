"""Support for MySensors sensors."""
from homeassistant.components import mysensors
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import (
    CONDUCTIVITY,
    DEGREE,
    ELECTRICAL_CURRENT_AMPERE,
    ELECTRICAL_VOLT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_METERS,
    MASS_KILOGRAMS,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
    VOLT,
)

SENSORS = {
    "V_TEMP": [None, "mdi:thermometer"],
    "V_HUM": [UNIT_PERCENTAGE, "mdi:water-percent"],
    "V_DIMMER": [UNIT_PERCENTAGE, "mdi:percent"],
    "V_PERCENTAGE": [UNIT_PERCENTAGE, "mdi:percent"],
    "V_PRESSURE": [None, "mdi:gauge"],
    "V_FORECAST": [None, "mdi:weather-partly-cloudy"],
    "V_RAIN": [None, "mdi:weather-rainy"],
    "V_RAINRATE": [None, "mdi:weather-rainy"],
    "V_WIND": [None, "mdi:weather-windy"],
    "V_GUST": [None, "mdi:weather-windy"],
    "V_DIRECTION": [DEGREE, "mdi:compass"],
    "V_WEIGHT": [MASS_KILOGRAMS, "mdi:weight-kilogram"],
    "V_DISTANCE": [LENGTH_METERS, "mdi:ruler"],
    "V_IMPEDANCE": ["ohm", None],
    "V_WATT": [POWER_WATT, None],
    "V_KWH": [ENERGY_KILO_WATT_HOUR, None],
    "V_LIGHT_LEVEL": [UNIT_PERCENTAGE, "mdi:white-balance-sunny"],
    "V_FLOW": [LENGTH_METERS, "mdi:gauge"],
    "V_VOLUME": ["m³", None],
    "V_LEVEL": {
        "S_SOUND": ["dB", "mdi:volume-high"],
        "S_VIBRATION": [FREQUENCY_HERTZ, None],
        "S_LIGHT_LEVEL": ["lx", "mdi:white-balance-sunny"],
    },
    "V_VOLTAGE": [VOLT, "mdi:flash"],
    "V_CURRENT": [ELECTRICAL_CURRENT_AMPERE, "mdi:flash-auto"],
    "V_PH": ["pH", None],
    "V_ORP": ["mV", None],
    "V_EC": [CONDUCTIVITY, None],
    "V_VAR": ["var", None],
    "V_VA": [ELECTRICAL_VOLT_AMPERE, None],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MySensors platform for sensors."""
    mysensors.setup_mysensors_platform(
        hass,
        DOMAIN,
        discovery_info,
        MySensorsSensor,
        async_add_entities=async_add_entities,
    )


class MySensorsSensor(mysensors.device.MySensorsEntity):
    """Representation of a MySensors Sensor child node."""

    @property
    def force_update(self):
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return True

    @property
    def state(self):
        """Return the state of the device."""
        return self._values.get(self.value_type)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        _, icon = self._get_sensor_type()
        return icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        set_req = self.gateway.const.SetReq
        if (
            float(self.gateway.protocol_version) >= 1.5
            and set_req.V_UNIT_PREFIX in self._values
        ):
            return self._values[set_req.V_UNIT_PREFIX]
        unit, _ = self._get_sensor_type()
        return unit

    def _get_sensor_type(self):
        """Return list with unit and icon of sensor type."""
        pres = self.gateway.const.Presentation
        set_req = self.gateway.const.SetReq
        SENSORS[set_req.V_TEMP.name][0] = (
            TEMP_CELSIUS if self.gateway.metric else TEMP_FAHRENHEIT
        )
        sensor_type = SENSORS.get(set_req(self.value_type).name, [None, None])
        if isinstance(sensor_type, dict):
            sensor_type = sensor_type.get(pres(self.child_type).name, [None, None])
        return sensor_type
