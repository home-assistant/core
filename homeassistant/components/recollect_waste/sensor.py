"""Support for ReCollect Waste sensors."""
from __future__ import annotations

from aiorecollect.client import PickupType

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, DEVICE_CLASS_DATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN

ATTR_PICKUP_TYPES = "pickup_types"
ATTR_AREA_NAME = "area_name"
ATTR_NEXT_PICKUP_TYPES = "next_pickup_types"
ATTR_NEXT_PICKUP_DATE = "next_pickup_date"

DEFAULT_NAME = "Waste Pickup"

PLATFORM_SCHEMA = cv.deprecated(DOMAIN)


@callback
def async_get_pickup_type_names(
    entry: ConfigEntry, pickup_types: list[PickupType]
) -> list[str]:
    """Return proper pickup type names from their associated objects."""
    return [
        t.friendly_name
        if entry.options.get(CONF_FRIENDLY_NAME) and t.friendly_name
        else t.name
        for t in pickup_types
    ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ReCollectWasteSensor(coordinator, entry)])


class ReCollectWasteSensor(CoordinatorEntity, SensorEntity):
    """ReCollect Waste Sensor."""

    _attr_device_class = DEVICE_CLASS_DATE

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_name = DEFAULT_NAME
        self._attr_unique_id = (
            f"{entry.data[CONF_PLACE_ID]}{entry.data[CONF_SERVICE_ID]}"
        )
        self._entry = entry

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        try:
            pickup_event = self.coordinator.data[0]
            next_pickup_event = self.coordinator.data[1]
        except IndexError:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_extra_state_attributes.update(
            {
                ATTR_PICKUP_TYPES: async_get_pickup_type_names(
                    self._entry, pickup_event.pickup_types
                ),
                ATTR_AREA_NAME: pickup_event.area_name,
                ATTR_NEXT_PICKUP_TYPES: async_get_pickup_type_names(
                    self._entry, next_pickup_event.pickup_types
                ),
                ATTR_NEXT_PICKUP_DATE: next_pickup_event.date.isoformat(),
            }
        )
        self._attr_native_value = pickup_event.date
