"""Sensors for National Weather Service (NWS)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import base_unique_id, device_info
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
    _attr_attribution = ATTRIBUTION

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
        if hass.config.units is US_CUSTOMARY_SYSTEM:
            self._attr_native_unit_of_measurement = description.unit_convert

    @property
    def native_value(self):
        """Return the state."""
        value = self._nws.observation.get(self.entity_description.key)
        if value is None:
            return None
        # Set alias to unit property -> prevent unnecessary hasattr calls
        unit_of_measurement = self.native_unit_of_measurement
        if unit_of_measurement == SPEED_MILES_PER_HOUR:
            return round(
                SpeedConverter.convert(
                    value, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR
                )
            )
        if unit_of_measurement == LENGTH_MILES:
            return round(DistanceConverter.convert(value, LENGTH_METERS, LENGTH_MILES))
        if unit_of_measurement == PRESSURE_INHG:
            return round(
                PressureConverter.convert(value, PRESSURE_PA, PRESSURE_INHG), 2
            )
        if unit_of_measurement == TEMP_CELSIUS:
            return round(value, 1)
        if unit_of_measurement == PERCENTAGE:
            return round(value)
        return value

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self._latitude, self._longitude)}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return device_info(self._latitude, self._longitude)
