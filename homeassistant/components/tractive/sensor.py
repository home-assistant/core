"""Support for Tractive sensors."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_DAILY_GOAL,
    ATTR_LIVE_TRACKING_REMAINING,
    ATTR_MINUTES_ACTIVE,
    ATTR_TRACKER_STATE,
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKER_ACTIVITY_STATUS_UPDATED,
    TRACKER_HARDWARE_STATUS_UPDATED,
)
from .entity import TractiveEntity


@dataclass
class TractiveSensorEntityDescription(SensorEntityDescription):
    """Class describing Tractive sensor entities."""

    attributes: tuple = ()
    entity_class: type[TractiveSensor] | None = None


class TractiveSensor(TractiveEntity, SensorEntity):
    """Tractive sensor."""

    def __init__(self, user_id, trackable, tracker_details, unique_id, description):
        """Initialize sensor entity."""
        super().__init__(user_id, trackable, tracker_details)

        self._attr_unique_id = unique_id
        self.entity_description = description

    @callback
    def handle_server_unavailable(self):
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()


class TractiveHardwareSensor(TractiveSensor):
    """Tractive hardware sensor."""

    def __init__(self, user_id, trackable, tracker_details, unique_id, description):
        """Initialize sensor entity."""
        super().__init__(user_id, trackable, tracker_details, unique_id, description)
        self._attr_name = f"{self._tracker_id} {description.name}"

    @callback
    def handle_hardware_status_update(self, event):
        """Handle hardware status update."""
        if (_state := event[self.entity_description.key]) is None:
            return
        self._attr_native_value = _state
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_HARDWARE_STATUS_UPDATED}-{self._tracker_id}",
                self.handle_hardware_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self.handle_server_unavailable,
            )
        )


class TractiveActivitySensor(TractiveSensor):
    """Tractive active sensor."""

    def __init__(self, user_id, trackable, tracker_details, unique_id, description):
        """Initialize sensor entity."""
        super().__init__(user_id, trackable, tracker_details, unique_id, description)
        self._attr_name = f"{trackable['details']['name']} {description.name}"

    @callback
    def handle_activity_status_update(self, event):
        """Handle activity status update."""
        self._attr_native_value = event[self.entity_description.key]
        self._attr_extra_state_attributes = {
            attr: event[attr] if attr in event else None
            for attr in self.entity_description.attributes
        }
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_ACTIVITY_STATUS_UPDATED}-{self._trackable['_id']}",
                self.handle_activity_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self.handle_server_unavailable,
            )
        )


SENSOR_TYPES = (
    TractiveSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        entity_class=TractiveHardwareSensor,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_LIVE_TRACKING_REMAINING,
        name="Live tracking remaining time",
        native_unit_of_measurement=TIME_SECONDS,
        entity_class=TractiveHardwareSensor,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_TRACKER_STATE,
        name="Tracker state",
        entity_class=TractiveHardwareSensor,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_MINUTES_ACTIVE,
        name="Minutes Active",
        icon="mdi:clock-time-eight-outline",
        native_unit_of_measurement=TIME_MINUTES,
        attributes=(ATTR_DAILY_GOAL,),
        entity_class=TractiveActivitySensor,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive sensors."""
    client = hass.data[DOMAIN][entry.entry_id]

    trackables = await client.trackable_objects()

    entities = []

    async def _prepare_sensor_entity(item):
        """Prepare sensor entities."""
        trackable = await item.details()
        tracker = client.tracker(trackable["device_id"])
        tracker_details = await tracker.details()
        for description in SENSOR_TYPES:
            unique_id = f"{trackable['_id']}_{description.key}"
            entities.append(
                description.entity_class(
                    client.user_id,
                    trackable,
                    tracker_details,
                    unique_id,
                    description,
                )
            )

    await asyncio.gather(*(_prepare_sensor_entity(item) for item in trackables))

    async_add_entities(entities)
