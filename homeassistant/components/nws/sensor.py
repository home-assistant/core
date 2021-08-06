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
    NWSSensorEntityDescription,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the NWS weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    station = entry.data[CONF_STATION]

    async_add_entities(
        NWSSensor(
            hass=hass,
            entry_data=entry.data,
            hass_data=hass_data,
            description=description,
            station=station,
        )
        for description in SENSOR_TYPES
    )


class NWSSensor(CoordinatorEntity, SensorEntity):
    """An NWS Sensor Entity."""

    entity_description: NWSSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data,
        hass_data,
        description: NWSSensorEntityDescription,
        station,
    ):
        """Initialise the platform with a data instance."""
        super().__init__(hass_data[COORDINATOR_OBSERVATION])
        self._nws = hass_data[NWS_DATA]
        self._latitude = entry_data[CONF_LATITUDE]
        self._longitude = entry_data[CONF_LONGITUDE]
        self.entity_description = description

        self._attr_name = f"{station} {description.name}"
        if not hass.config.units.is_metric:
            self._attr_unit_of_measurement = description.unit_convert

    @property
    def state(self):
        """Return the state."""
        value = self._nws.observation.get(self.entity_description.key)
        if value is None:
            return None
        # Set alias to unit property -> prevent unnecessary hasattr calls
        unit_of_measurement = self.unit_of_measurement
        if unit_of_measurement == SPEED_MILES_PER_HOUR:
            return round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES))
        if unit_of_measurement == LENGTH_MILES:
            return round(convert_distance(value, LENGTH_METERS, LENGTH_MILES))
        if unit_of_measurement == PRESSURE_INHG:
            return round(convert_pressure(value, PRESSURE_PA, PRESSURE_INHG), 2)
        if unit_of_measurement == TEMP_CELSIUS:
            return round(value, 1)
        if unit_of_measurement == PERCENTAGE:
            return round(value)
        return value

    @property
    def device_state_attributes(self):
        """Return the attribution."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self._latitude, self._longitude)}_{self.entity_description.key}"

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
