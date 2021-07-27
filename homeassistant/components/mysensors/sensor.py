"""Support for MySensors sensors."""
from __future__ import annotations

from datetime import datetime

from awesomeversion import AwesomeVersion

from homeassistant.components import mysensors
from homeassistant.components.sensor import (
    DOMAIN,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONDUCTIVITY,
    DEGREE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_METERS,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    SOUND_PRESSURE_DB,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .helpers import on_unload

SENSORS: dict[str, list[str | None] | dict[str, list[str | None]]] = {
    "V_TEMP": [None, None, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT],
    "V_HUM": [
        PERCENTAGE,
        "mdi:water-percent",
        DEVICE_CLASS_HUMIDITY,
        STATE_CLASS_MEASUREMENT,
    ],
    "V_DIMMER": [PERCENTAGE, "mdi:percent", None, None],
    "V_PERCENTAGE": [PERCENTAGE, "mdi:percent", None, None],
    "V_PRESSURE": [None, "mdi:gauge", None, None],
    "V_FORECAST": [None, "mdi:weather-partly-cloudy", None, None],
    "V_RAIN": [None, "mdi:weather-rainy", None, None],
    "V_RAINRATE": [None, "mdi:weather-rainy", None, None],
    "V_WIND": [None, "mdi:weather-windy", None, None],
    "V_GUST": [None, "mdi:weather-windy", None, None],
    "V_DIRECTION": [DEGREE, "mdi:compass", None, None],
    "V_WEIGHT": [MASS_KILOGRAMS, "mdi:weight-kilogram", None, None],
    "V_DISTANCE": [LENGTH_METERS, "mdi:ruler", None, None],
    "V_IMPEDANCE": ["ohm", None, None, None],
    "V_WATT": [POWER_WATT, None, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT],
    "V_KWH": [
        ENERGY_KILO_WATT_HOUR,
        None,
        DEVICE_CLASS_ENERGY,
        STATE_CLASS_MEASUREMENT,
    ],
    "V_LIGHT_LEVEL": [PERCENTAGE, "mdi:white-balance-sunny", None, None],
    "V_FLOW": [LENGTH_METERS, "mdi:gauge", None, None],
    "V_VOLUME": [VOLUME_CUBIC_METERS, None, None, None],
    "V_LEVEL": {
        "S_SOUND": [SOUND_PRESSURE_DB, "mdi:volume-high", None, None],
        "S_VIBRATION": [FREQUENCY_HERTZ, None, None, None],
        "S_LIGHT_LEVEL": [
            LIGHT_LUX,
            "mdi:white-balance-sunny",
            DEVICE_CLASS_ILLUMINANCE,
            STATE_CLASS_MEASUREMENT,
        ],
    },
    "V_VOLTAGE": [
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:flash",
        DEVICE_CLASS_VOLTAGE,
        STATE_CLASS_MEASUREMENT,
    ],
    "V_CURRENT": [
        ELECTRIC_CURRENT_AMPERE,
        "mdi:flash-auto",
        DEVICE_CLASS_CURRENT,
        STATE_CLASS_MEASUREMENT,
    ],
    "V_PH": ["pH", None, None, None],
    "V_ORP": [ELECTRIC_POTENTIAL_MILLIVOLT, None, None, None],
    "V_EC": [CONDUCTIVITY, None, None, None],
    "V_VAR": ["var", None, None, None],
    "V_VA": [POWER_VOLT_AMPERE, None, None, None],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors sensor."""
        mysensors.setup_mysensors_platform(
            hass,
            DOMAIN,
            discovery_info,
            MySensorsSensor,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, DOMAIN),
            async_discover,
        ),
    )


class MySensorsSensor(mysensors.device.MySensorsEntity, SensorEntity):
    """Representation of a MySensors Sensor child node."""

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return True

    @property
    def state(self) -> str | None:
        """Return the state of this entity."""
        return self._values.get(self.value_type)

    @property
    def device_class(self) -> str | None:
        """Return the device class of this entity."""
        return self._get_sensor_type()[2]

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return self._get_sensor_type()[1]

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        set_req = self.gateway.const.SetReq

        if set_req(self.value_type).name == "V_KWH":
            return utc_from_timestamp(0)
        return None

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity."""
        return self._get_sensor_type()[3]

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        set_req = self.gateway.const.SetReq
        if (
            AwesomeVersion(self.gateway.protocol_version) >= AwesomeVersion("1.5")
            and set_req.V_UNIT_PREFIX in self._values
        ):
            custom_unit: str = self._values[set_req.V_UNIT_PREFIX]
            return custom_unit

        if set_req(self.value_type) == set_req.V_TEMP:
            if self.hass.config.units.is_metric:
                return TEMP_CELSIUS
            return TEMP_FAHRENHEIT

        unit = self._get_sensor_type()[0]
        return unit

    def _get_sensor_type(self) -> list[str | None]:
        """Return list with unit and icon of sensor type."""
        pres = self.gateway.const.Presentation
        set_req = self.gateway.const.SetReq

        _sensor_type = SENSORS.get(
            set_req(self.value_type).name, [None, None, None, None]
        )
        if isinstance(_sensor_type, dict):
            sensor_type = _sensor_type.get(
                pres(self.child_type).name, [None, None, None, None]
            )
        else:
            sensor_type = _sensor_type
        return sensor_type
