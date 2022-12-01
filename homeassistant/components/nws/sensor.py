"""Sensors for National Weather Service (NWS)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

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

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self._nws.observation.get(self.entity_description.key)

    @property
    def unique_id(self) -> str:
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
