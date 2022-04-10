"""Support for Renault device trackers."""
from __future__ import annotations

from renault_api.kamereon.models import KamereonVehicleLocationData

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .renault_entities import RenaultDataEntity, RenaultDataEntityDescription
from .renault_hub import RenaultHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultDeviceTracker] = [
        RenaultDeviceTracker(vehicle, description)
        for vehicle in proxy.vehicles.values()
        for description in DEVICE_TRACKER_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultDeviceTracker(
    RenaultDataEntity[KamereonVehicleLocationData], TrackerEntity
):
    """Mixin for device tracker specific attributes."""

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.coordinator.data.gpsLatitude if self.coordinator.data else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.coordinator.data.gpsLongitude if self.coordinator.data else None

    @property
    def source_type(self) -> str:
        """Return the source type of the device."""
        return SOURCE_TYPE_GPS


DEVICE_TRACKER_TYPES: tuple[RenaultDataEntityDescription, ...] = (
    RenaultDataEntityDescription(
        key="location",
        coordinator="location",
        icon="mdi:car",
        name="Location",
    ),
)
