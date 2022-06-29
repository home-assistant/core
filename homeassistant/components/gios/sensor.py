"""Support for the GIOS service."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import DOMAIN as PLATFORM, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_NAME, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    ATTR_AQI,
    ATTR_INDEX,
    ATTR_PM25,
    ATTR_STATION,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
    URL,
)
from .model import GiosSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a GIOS entities from a config_entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of one sensor, it is necessary to migrate
    # the unique_id to the new name.
    entity_registry = er.async_get(hass)
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

    for description in SENSOR_TYPES:
        if getattr(coordinator.data, description.key) is None:
            continue
        if description.key == ATTR_AQI:
            sensors.append(GiosAqiSensor(name, coordinator, description))
        else:
            sensors.append(GiosSensor(name, coordinator, description))
    async_add_entities(sensors)


class GiosSensor(CoordinatorEntity[GiosDataUpdateCoordinator], SensorEntity):
    """Define an GIOS sensor."""

    entity_description: GiosSensorEntityDescription

    def __init__(
        self,
        name: str,
        coordinator: GiosDataUpdateCoordinator,
        description: GiosSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(coordinator.gios.station_id))},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
            configuration_url=URL.format(station_id=coordinator.gios.station_id),
        )
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{coordinator.gios.station_id}-{description.key}"
        self._attrs: dict[str, Any] = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.gios.station_name,
        }
        self.entity_description = description

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        self._attrs[ATTR_NAME] = getattr(
            self.coordinator.data, self.entity_description.key
        ).name
        self._attrs[ATTR_INDEX] = getattr(
            self.coordinator.data, self.entity_description.key
        ).index
        return self._attrs

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        state = getattr(self.coordinator.data, self.entity_description.key).value
        assert self.entity_description.value is not None
        return cast(StateType, self.entity_description.value(state))


class GiosAqiSensor(GiosSensor):
    """Define an GIOS AQI sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key).value
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available
        return available and bool(
            getattr(self.coordinator.data, self.entity_description.key)
        )
