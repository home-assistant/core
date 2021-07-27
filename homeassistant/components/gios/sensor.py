"""Support for the GIOS service."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as PLATFORM,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_NAME, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    ATTR_AQI,
    ATTR_INDEX,
    ATTR_PM25,
    ATTR_STATION,
    ATTR_UNIT,
    ATTR_VALUE,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a GIOS entities from a config_entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of one sensor, it is necessary to migrate
    # the unique_id to the new name.
    entity_registry = await async_get_registry(hass)
    old_unique_id = f"{coordinator.gios.station_id}-pm2.5"
    if entity_id := entity_registry.async_get_entity_id(
        PLATFORM, DOMAIN, old_unique_id
    ):
        new_unique_id = f"{coordinator.gios.station_id}-{ATTR_PM25}"
        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    sensors: list[GiosSensor | GiosAqiSensor] = []

    for sensor in SENSOR_TYPES.keys():
        if getattr(coordinator.data, sensor) is None:
            continue
        if sensor == ATTR_AQI:
            sensors.append(GiosAqiSensor(name, sensor, coordinator))
        else:
            sensors.append(GiosSensor(name, sensor, coordinator))
    async_add_entities(sensors)


class GiosSensor(CoordinatorEntity, SensorEntity):
    """Define an GIOS sensor."""

    coordinator: GiosDataUpdateCoordinator

    def __init__(
        self, name: str, sensor_type: str, coordinator: GiosDataUpdateCoordinator
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._description = SENSOR_TYPES[sensor_type]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(coordinator.gios.station_id))},
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }
        self._attr_icon = "mdi:blur"
        if sensor_type == ATTR_PM25:
            self._attr_name = f"{name} PM2.5"
        else:
            self._attr_name = f"{name} {sensor_type.upper()}"
        self._attr_state_class = self._description.get(ATTR_STATE_CLASS)
        self._attr_unique_id = f"{coordinator.gios.station_id}-{sensor_type}"
        self._attr_unit_of_measurement = self._description.get(ATTR_UNIT)
        self._sensor_type = sensor_type
        self._attrs: dict[str, Any] = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.gios.station_name,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        self._attrs[ATTR_NAME] = getattr(self.coordinator.data, self._sensor_type).name
        self._attrs[ATTR_INDEX] = getattr(
            self.coordinator.data, self._sensor_type
        ).index
        return self._attrs

    @property
    def state(self) -> StateType:
        """Return the state."""
        state = getattr(self.coordinator.data, self._sensor_type).value
        return cast(StateType, self._description[ATTR_VALUE](state))


class GiosAqiSensor(GiosSensor):
    """Define an GIOS AQI sensor."""

    @property
    def state(self) -> StateType:
        """Return the state."""
        return cast(StateType, getattr(self.coordinator.data, self._sensor_type).value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available
        return available and bool(getattr(self.coordinator.data, self._sensor_type))
