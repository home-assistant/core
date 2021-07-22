"""Sensors for National Weather Service (NWS)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.dt import utcnow
from homeassistant.util.pressure import convert as convert_pressure

from . import base_unique_id
from .const import (
    ATTRIBUTION,
    CONF_STATION,
    COORDINATOR_OBSERVATION,
    DOMAIN,
    NWS_DATA,
    OBSERVATION_VALID_TIME,
    SENSOR_TYPES,
    NWSSensorMetadata,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the NWS weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    station = entry.data[CONF_STATION]

    entities = []
    for sensor_type, metadata in SENSOR_TYPES.items():
        entities.append(
            NWSSensor(
                hass,
                entry.data,
                hass_data,
                sensor_type,
                metadata,
                station,
            ),
        )

    async_add_entities(entities, False)


class NWSSensor(CoordinatorEntity, SensorEntity):
    """An NWS Sensor Entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data,
        hass_data,
        sensor_type,
        metadata: NWSSensorMetadata,
        station,
    ):
        """Initialise the platform with a data instance."""
        super().__init__(hass_data[COORDINATOR_OBSERVATION])
        self._nws = hass_data[NWS_DATA]
        self._latitude = entry_data[CONF_LATITUDE]
        self._longitude = entry_data[CONF_LONGITUDE]
        self._type = sensor_type
        self._metadata = metadata

        self._attr_name = f"{station} {metadata.label}"
        self._attr_icon = metadata.icon
        self._attr_device_class = metadata.device_class
        if hass.config.units.is_metric:
            self._attr_unit_of_measurement = metadata.unit
        else:
            self._attr_unit_of_measurement = metadata.unit_convert

    @property
    def state(self):
        """Return the state."""
        value = self._nws.observation.get(self._type)
        if value is None:
            return None
        if self._attr_unit_of_measurement == SPEED_MILES_PER_HOUR:
            return round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES))
        if self._attr_unit_of_measurement == LENGTH_MILES:
            return round(convert_distance(value, LENGTH_METERS, LENGTH_MILES))
        if self._attr_unit_of_measurement == PRESSURE_INHG:
            return round(convert_pressure(value, PRESSURE_PA, PRESSURE_INHG), 2)
        if self._attr_unit_of_measurement == TEMP_CELSIUS:
            return round(value, 1)
        if self._attr_unit_of_measurement == PERCENTAGE:
            return round(value)
        return value

    @property
    def device_state_attributes(self):
        """Return the attribution."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

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
