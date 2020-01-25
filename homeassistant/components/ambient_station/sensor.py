"""Support for Ambient Weather Station sensors."""
import logging

from homeassistant.const import ATTR_NAME

from . import (
    SENSOR_TYPES,
    TYPE_SOLARRADIATION,
    TYPE_SOLARRADIATION_LX,
    AmbientWeatherEntity,
)
from .const import (
    ATTR_LAST_DATA,
    ATTR_MONITORED_CONDITIONS,
    DATA_CLIENT,
    DOMAIN,
    TYPE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in station[ATTR_MONITORED_CONDITIONS]:
            name, unit, kind, device_class = SENSOR_TYPES[condition]
            if kind == TYPE_SENSOR:
                sensor_list.append(
                    AmbientWeatherSensor(
                        ambient,
                        mac_address,
                        station[ATTR_NAME],
                        condition,
                        name,
                        device_class,
                        unit,
                    )
                )

    async_add_entities(sensor_list, True)


class AmbientWeatherSensor(AmbientWeatherEntity):
    """Define an Ambient sensor."""

    def __init__(
        self,
        ambient,
        mac_address,
        station_name,
        sensor_type,
        sensor_name,
        device_class,
        unit,
    ):
        """Initialize the sensor."""
        super().__init__(
            ambient, mac_address, station_name, sensor_type, sensor_name, device_class
        )

        self._unit = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        if self._sensor_type == TYPE_SOLARRADIATION_LX:
            # If the user requests the solarradiation_lx sensor, use the
            # value of the solarradiation sensor and apply a very accurate
            # approximation of converting sunlight W/m^2 to lx:
            w_m2_brightness_val = self._ambient.stations[self._mac_address][
                ATTR_LAST_DATA
            ].get(TYPE_SOLARRADIATION)
            self._state = round(float(w_m2_brightness_val) / 0.0079)
        else:
            self._state = self._ambient.stations[self._mac_address][ATTR_LAST_DATA].get(
                self._sensor_type
            )
