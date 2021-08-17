"""Support for Renault sensors."""
from __future__ import annotations

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .renault_entities import RenaultDataEntity, RenaultLocationDataEntity
from .renault_hub import RenaultHub
from .renault_vehicle import RenaultVehicleProxy


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities = get_entities(proxy)
    async_add_entities(entities)


def get_entities(proxy: RenaultHub) -> list[RenaultDataEntity]:
    """Create Renault entities for all vehicles."""
    entities = []
    for vehicle in proxy.vehicles.values():
        entities.extend(get_vehicle_entities(vehicle))
    return entities


def get_vehicle_entities(vehicle: RenaultVehicleProxy) -> list[RenaultDataEntity]:
    """Create Renault entities for single vehicle."""
    entities: list[RenaultDataEntity] = []
    if "location" in vehicle.coordinators:
        entities.append(RenaultLocationSensor(vehicle, "Location"))
    return entities


class RenaultLocationSensor(RenaultLocationDataEntity, TrackerEntity):
    """Location sensor."""

    _attr_icon = "mdi:car"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.data.gpsLatitude if self.data else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.data.gpsLongitude if self.data else None

    @property
    def source_type(self) -> str:
        """Return the source type of the device."""
        return SOURCE_TYPE_GPS
