"""Sensors for National Weather Service (NWS)."""
import logging

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_MILES_PER_HOUR,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.dt import utcnow
from homeassistant.util.pressure import convert as convert_pressure

from . import base_unique_id
from .const import (
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_UNIT,
    ATTR_UNIT_CONVERT,
    ATTRIBUTION,
    CONF_STATION,
    COORDINATOR_OBSERVATION,
    DOMAIN,
    NWS_DATA,
    OBSERVATION_VALID_TIME,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the NWS weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    station = entry.data[CONF_STATION]
    for sensor_name, sensor_data in SENSOR_TYPES.items():
        if hass.config.units.is_metric:
            unit = sensor_data[ATTR_UNIT]
        else:
            unit = sensor_data[ATTR_UNIT_CONVERT]
        async_add_entities(
            [
                NWSSensor(
                    entry.data,
                    hass_data,
                    sensor_name,
                    station,
                    sensor_data[ATTR_LABEL],
                    sensor_data[ATTR_ICON],
                    sensor_data[ATTR_DEVICE_CLASS],
                    unit,
                ),
            ],
            False,
        )


class NWSSensor(Entity):
    """An NWS Sensor Entity."""

    def __init__(
        self, entry_data, hass_data, name, station, label, icon, device_class, unit
    ):
        """Initialise the platform with a data instance."""
        self._nws = hass_data[NWS_DATA]
        self._latitude = entry_data[CONF_LATITUDE]
        self._longitude = entry_data[CONF_LONGITUDE]
        self._coordinator = hass_data[COORDINATOR_OBSERVATION]
        self._name = name
        self._station = station
        self._label = label
        self._icon = icon
        self._device_class = device_class
        self._unit = unit

    @property
    def state(self):
        """Return the state."""
        value = self._nws.observation.get(self._name)
        if value is None:
            return None
        if self._unit == SPEED_MILES_PER_HOUR:
            return round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES))
        if self._unit == LENGTH_MILES:
            return round(convert_distance(value, LENGTH_METERS, LENGTH_MILES))
        if self._unit == PRESSURE_INHG:
            return round(convert_pressure(value, PRESSURE_PA, PRESSURE_INHG), 2)
        return value

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return f"{self._station} {self._label}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self._latitude, self._longitude)}_{self._name}"

    @property
    def available(self):
        """Return if state is available."""
        if self._coordinator.last_update_success_time:
            last_success_time = (
                utcnow() - self._coordinator.last_update_success_time
                < OBSERVATION_VALID_TIME
            )
        else:
            last_success_time = False
        return self._coordinator.last_update_success or last_success_time

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False
