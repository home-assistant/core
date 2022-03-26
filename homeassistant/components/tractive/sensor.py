"""Support for Tractive sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, PERCENTAGE, TIME_MINUTES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Trackables
from .const import (
    ATTR_DAILY_GOAL,
    ATTR_MINUTES_ACTIVE,
    ATTR_TRACKER_STATE,
    CLIENT,
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKABLES,
    TRACKER_ACTIVITY_STATUS_UPDATED,
    TRACKER_HARDWARE_STATUS_UPDATED,
)
from .entity import TractiveEntity


@dataclass
class TractiveRequiredKeysMixin:
    """Mixin for required keys."""

    entity_class: type[TractiveSensor]


@dataclass
class TractiveSensorEntityDescription(
    SensorEntityDescription, TractiveRequiredKeysMixin
):
    """Class describing Tractive sensor entities."""


class TractiveSensor(TractiveEntity, SensorEntity):
    """Tractive sensor."""

    def __init__(
        self,
        user_id: str,
        item: Trackables,
        description: TractiveSensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(user_id, item.trackable, item.tracker_details)

        self._attr_name = f"{item.trackable['details']['name']} {description.name}"
        self._attr_unique_id = f"{item.trackable['_id']}_{description.key}"
        self.entity_description = description

    @callback
    def handle_server_unavailable(self) -> None:
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()


class TractiveHardwareSensor(TractiveSensor):
    """Tractive hardware sensor."""

    @callback
    def handle_hardware_status_update(self, event: dict[str, Any]) -> None:
        """Handle hardware status update."""
        if (_state := event[self.entity_description.key]) is None:
            return
        self._attr_native_value = _state
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
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

    @callback
    def handle_activity_status_update(self, event: dict[str, Any]) -> None:
        """Handle activity status update."""
        self._attr_native_value = event[self.entity_description.key]
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
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


SENSOR_TYPES: tuple[TractiveSensorEntityDescription, ...] = (
    TractiveSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_class=TractiveHardwareSensor,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TractiveSensorEntityDescription(
        # Currently, only state operational and not_reporting are used
        # More states are available by polling the data
        key=ATTR_TRACKER_STATE,
        name="Tracker state",
        device_class="tractive__tracker_state",
        entity_class=TractiveHardwareSensor,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_MINUTES_ACTIVE,
        name="Minutes Active",
        icon="mdi:clock-time-eight-outline",
        native_unit_of_measurement=TIME_MINUTES,
        entity_class=TractiveActivitySensor,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_DAILY_GOAL,
        name="Daily Goal",
        icon="mdi:flag-checkered",
        native_unit_of_measurement=TIME_MINUTES,
        entity_class=TractiveActivitySensor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    trackables = hass.data[DOMAIN][entry.entry_id][TRACKABLES]

    entities = [
        description.entity_class(client.user_id, item, description)
        for description in SENSOR_TYPES
        for item in trackables
    ]

    async_add_entities(entities)
