"""Support for Tractive binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Trackables, TractiveClient, TractiveConfigEntry
from .const import TRACKER_HARDWARE_STATUS_UPDATED
from .entity import TractiveEntity


class TractiveBinarySensor(TractiveEntity, BinarySensorEntity):
    """Tractive sensor."""

    def __init__(
        self,
        client: TractiveClient,
        item: Trackables,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(
            client,
            item.trackable,
            item.tracker_details,
            f"{TRACKER_HARDWARE_STATUS_UPDATED}-{item.tracker_details['_id']}",
        )

        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self._attr_available = False
        self.entity_description = description

    @callback
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle status update."""
        self._attr_is_on = event[self.entity_description.key]

        super().handle_status_update(event)


SENSOR_TYPE = BinarySensorEntityDescription(
    key=ATTR_BATTERY_CHARGING,
    translation_key="tracker_battery_charging",
    device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tractive device trackers."""
    client = entry.runtime_data.client
    trackables = entry.runtime_data.trackables

    entities = [
        TractiveBinarySensor(client, item, SENSOR_TYPE)
        for item in trackables
        if item.tracker_details.get("charging_state") is not None
    ]

    async_add_entities(entities)
