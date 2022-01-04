"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.intellifire import IntellifireDataUpdateCoordinator
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...config_entries import ConfigEntry
from .const import (
    DOMAIN,
    FAN_SPEED,
    FLAME_HEIGHT,
    INTELLIFIRE_SENSORS,
    TEMP,
    THERMOSTAT_TARGET,
    TIMER_TIME,
)

ATTRIBUTION = "Data provided by unpublished Intellifire API"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:

    id = entry.entry_id
    coordinator = hass.data[DOMAIN][id]
    entities = [
        IntellifireSensor(coordinator=coordinator, entry_id=id, description=description)
        for description in INTELLIFIRE_SENSORS
    ]

    async_add_entities(entities)


class IntellifireSensor(CoordinatorEntity, SensorEntity):
    """Define a generic class for Sensors"""

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        entry_id,
        description: SensorEntityDescription,
    ) -> None:
        """Init the sensor"""
        super().__init__(coordinator)
        self.coordinator = coordinator

        self.entity_description = description
        self._state = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_name = f"{coordinator.intellifire_name} Fireplace {description.name}"
        self._attr_unique_id = (
            f"Intellifire_{coordinator.safe_intellifire_name}_{description.key}"
        )

    @property
    def native_value(self):
        """Return the state"""
        sensor_type = self.entity_description.key
        data = self.coordinator.api.data
        if sensor_type == FLAME_HEIGHT:
            return data.flameheight
        if sensor_type == FAN_SPEED:
            return data.fanspeed
        if sensor_type == TIMER_TIME:
            # if data.timer_on == 1:
            # Convert time remaining into minutes
            return round(int(data.timeremaining_s) / 60)
        if sensor_type == THERMOSTAT_TARGET:
            return data.thermostat_setpoint_c
        if sensor_type == TEMP:
            return data.temperature_c


#
# def __init__(
#        self,
#        coordinator: AirNowDataUpdateCoordinator,
#        description: SensorEntityDescription,
#    ) -> None:
#        """Initialize."""
#        super().__init__(coordinator)
#        self.entity_description = description
#        self._state = None
#        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
#        self._attr_name = f"AirNow {description.name}"
#        self._attr_unique_id = (
#            f"{coordinator.latitude}-{coordinator.longitude}-{description.key.lower()}"
#        )
#
#    @property
#    def native_value(self):
#        """Return the state."""
#        self._state = self.coordinator.data.get(self.entity_description.key)
#
#        return self._state
#
#    @property
#    def extra_state_attributes(self):
#        """Return the state attributes."""
#        if self.entity_description.key == ATTR_API_AQI:
#            self._attrs[SENSOR_AQI_ATTR_DESCR] = self.coordinator.data[
#                ATTR_API_AQI_DESCRIPTION
#            ]
#            self._attrs[SENSOR_AQI_ATTR_LEVEL] = self.coordinator.data[
#                ATTR_API_AQI_LEVEL
#            ]
#
#        return self._attrs
