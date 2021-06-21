"""Sensors for National Weather Service (NWS)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the NWS weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    station = entry.data[CONF_STATION]

    entities = []
    for sensor_type, sensor_data in SENSOR_TYPES.items():
        if hass.config.units.is_metric:
            unit = sensor_data[ATTR_UNIT]
        else:
            unit = sensor_data[ATTR_UNIT_CONVERT]
        entities.append(
            NWSSensor(
                entry.data,
                hass_data,
                sensor_type,
                station,
                sensor_data[ATTR_LABEL],
                sensor_data[ATTR_ICON],
                sensor_data[ATTR_DEVICE_CLASS],
                unit,
            ),
        )

    async_add_entities(entities, False)


class NWSSensor(CoordinatorEntity, SensorEntity):
    """An NWS Sensor Entity."""

    def __init__(
        self,
        entry_data,
        hass_data,
        sensor_type,
        station,
        label,
        icon,
        device_class,
        unit,
    ):
        """Initialise the platform with a data instance."""
        super().__init__(hass_data[COORDINATOR_OBSERVATION])
        self._nws = hass_data[NWS_DATA]
        self._latitude = entry_data[CONF_LATITUDE]
        self._longitude = entry_data[CONF_LONGITUDE]
        self._type = sensor_type
        self._station = station
        self._label = label
        self._icon = icon
        self._device_class = device_class
        self._unit = unit

    @property
    def state(self):
        """Return the state."""
        value = self._nws.observation.get(self._type)
        if value is None:
            return None
        if self._unit == SPEED_MILES_PER_HOUR:
            return round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES))
        if self._unit == LENGTH_MILES:
            return round(convert_distance(value, LENGTH_METERS, LENGTH_MILES))
        if self._unit == PRESSURE_INHG:
            return round(convert_pressure(value, PRESSURE_PA, PRESSURE_INHG), 2)
        if self._unit == TEMP_CELSIUS:
            return round(value, 1)
        if self._unit == PERCENTAGE:
            return round(value)
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

    @property
    def device_state_attributes(self):
        """Return the attribution."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the station."""
        return f"{self._station} {self._label}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self._latitude, self._longitude)}_{self._type}"

    @property
    def available(self):
        """Return if state is available."""
        if self.coordinator.last_update_success_time:
            last_success_time = (
                utcnow() - self.coordinator.last_update_success_time
                < OBSERVATION_VALID_TIME
            )
        else:
            last_success_time = False
        return self.coordinator.last_update_success or last_success_time

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False
