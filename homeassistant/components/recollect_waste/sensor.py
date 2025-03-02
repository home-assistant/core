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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
        translation_key=SENSOR_TYPE_CURRENT_PICKUP,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_NEXT_PICKUP,
        translation_key=SENSOR_TYPE_NEXT_PICKUP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    PICKUP_INDEX_MAP = {
        SENSOR_TYPE_CURRENT_PICKUP: 1,
        SENSOR_TYPE_NEXT_PICKUP: 2,
    }

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
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        relevant_events = (e for e in self.coordinator.data if e.date >= date.today())
        pickup_index = self.PICKUP_INDEX_MAP[self.entity_description.key]

        try:
            for _ in range(pickup_index):
                event = next(relevant_events)
        except StopIteration:
            LOGGER.debug("No pickup event found for %s", self.entity_description.key)
            self._attr_extra_state_attributes = {}
            self._attr_native_value = None
        else:
            self._attr_extra_state_attributes[ATTR_AREA_NAME] = event.area_name
            self._attr_extra_state_attributes[ATTR_PICKUP_TYPES] = (
                async_get_pickup_type_names(self._entry, event.pickup_types)
            )
            self._attr_native_value = event.date

        super()._handle_coordinator_update()
