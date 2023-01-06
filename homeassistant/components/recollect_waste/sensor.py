"""Support for ReCollect Waste sensors."""
from __future__ import annotations

from datetime import date

from aiorecollect.client import PickupEvent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER
from .entity import ReCollectWasteEntity
from .util import async_get_pickup_type_names

ATTR_PICKUP_TYPES = "pickup_types"
ATTR_AREA_NAME = "area_name"

SENSOR_TYPE_CURRENT_PICKUP = "current_pickup"
SENSOR_TYPE_NEXT_PICKUP = "next_pickup"

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_PICKUP,
        name="Current pickup",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_NEXT_PICKUP,
        name="Next pickup",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator: DataUpdateCoordinator[list[PickupEvent]] = hass.data[DOMAIN][
        entry.entry_id
    ]

    async_add_entities(
        ReCollectWasteSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class ReCollectWasteSensor(ReCollectWasteEntity, SensorEntity):
    """Define a ReCollect Waste sensor."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[PickupEvent]],
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{self._identifier}_{description.key}"
        self.entity_description = description

    @callback
    def _async_write_state_from_event(self, event: PickupEvent) -> None:
        """Write the entity state from a pickup event."""
        pickup_types = async_get_pickup_type_names(self._entry, event.pickup_types)
        self._attr_extra_state_attributes.update(
            {
                ATTR_AREA_NAME: event.area_name,
                ATTR_PICKUP_TYPES: pickup_types,
            }
        )
        self._attr_native_value = event.date

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            current_event = next(
                event for event in self.coordinator.data if event.date >= date.today()
            )
        except StopIteration:
            LOGGER.error("No current pickup found")
            return

        if self.entity_description.key == SENSOR_TYPE_CURRENT_PICKUP:
            self._async_write_state_from_event(current_event)
        else:
            try:
                next_event = next(
                    event
                    for event in self.coordinator.data
                    if event.date > current_event.date
                )
            except StopIteration:
                LOGGER.info("No next pickup found")
                return

            self._async_write_state_from_event(next_event)
