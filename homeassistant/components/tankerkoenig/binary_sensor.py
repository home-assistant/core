"""Tankerkoenig binary sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TankerkoenigDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the tankerkoenig binary sensors."""

    coordinator: TankerkoenigDataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id]

    stations = coordinator.stations.values()
    entities = []
    for station in stations:
        sensor = StationOpenBinarySensorEntity(
            station,
            coordinator,
            coordinator.show_on_map,
        )
        entities.append(sensor)
    _LOGGER.debug("Added sensors %s", entities)

    async_add_entities(entities)


class StationOpenBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Shows if a station is open or closed."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        station: dict,
        coordinator: TankerkoenigDataUpdateCoordinator,
        show_on_map: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station_id = station["id"]
        self._attr_name = (
            f"{station['brand']} {station['street']} {station['houseNumber']} status"
        )
        self._attr_unique_id = f"{station['id']}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(ATTR_ID, station["id"])},
            name=f"{station['brand']} {station['street']} {station['houseNumber']}",
            model=station["brand"],
            configuration_url="https://www.tankerkoenig.de",
        )
        if show_on_map:
            self._attr_extra_state_attributes = {
                ATTR_LATITUDE: station["lat"],
                ATTR_LONGITUDE: station["lng"],
            }

    @property
    def is_on(self) -> bool | None:
        """Return true if the station is open."""
        data = self.coordinator.data[self._station_id]
        return data is not None and "status" in data
