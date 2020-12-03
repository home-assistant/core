"""Support for Renault sensors."""
from typing import List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.distance import LENGTH_KILOMETERS

from .const import DOMAIN
from .renault_entities import RenaultCockpitDataEntity, RenaultDataEntity
from .renault_hub import RenaultHub
from .renault_vehicle import RenaultVehicleProxy


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.unique_id]
    entities = await get_entities(proxy)
    async_add_entities(entities)


async def get_entities(proxy: RenaultHub) -> List[RenaultDataEntity]:
    """Create Renault entities for all vehicles."""
    entities = []
    for vehicle in proxy.vehicles.values():
        entities.extend(await get_vehicle_entities(vehicle))
    return entities


async def get_vehicle_entities(vehicle: RenaultVehicleProxy) -> List[RenaultDataEntity]:
    """Create Renault entities for single vehicle."""
    entities = []
    if "cockpit" in vehicle.coordinators.keys():
        entities.append(RenaultMileageSensor(vehicle, "Mileage"))
    return entities


class RenaultMileageSensor(RenaultCockpitDataEntity):
    """Mileage sensor."""

    @property
    def state(self) -> Optional[int]:
        """Return the state of this entity."""
        if self.data.totalMileage is None:
            return None
        return round(self.data.totalMileage)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return LENGTH_KILOMETERS
