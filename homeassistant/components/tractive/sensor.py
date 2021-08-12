"""Support for Tractive sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    TIME_MINUTES,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_DAILY_GOAL,
    ATTR_MINUTES_ACTIVE,
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKER_ACTIVITY_STATUS_UPDATED,
    TRACKER_HARDWARE_STATUS_UPDATED,
)
from .model import TractiveEntity, TractiveSensorEntityDescription

ATTR_ACTIVITY = "activity"
ATTR_HARDWARE = "hardware"

SENSOR_TYPES = (
    TractiveSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        event_type=ATTR_HARDWARE,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_MINUTES_ACTIVE,
        name="Minutes Active",
        icon="mdi:clock-time-eight-outline",
        native_unit_of_measurement=TIME_MINUTES,
        event_type=ATTR_ACTIVITY,
        attributes=(ATTR_DAILY_GOAL,),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id]

    trackables = await client.trackable_objects()

    entities = []

    for item in trackables:
        trackable = await item.details()
        tracker = client.tracker(trackable["device_id"])
        tracker_details = await tracker.details()
        for description in SENSOR_TYPES:
            unique_id = f"{trackable['_id']}_{description.key}"
            if description.event_type == ATTR_HARDWARE:
                entities.append(
                    TractiveHardwareSensor(
                        client.user_id,
                        trackable,
                        tracker_details,
                        unique_id,
                        description,
                    )
                )
            if description.event_type == ATTR_ACTIVITY:
                entities.append(
                    TractiveActivitySensor(
                        client.user_id,
                        trackable,
                        tracker_details,
                        unique_id,
                        description,
                    )
                )

    async_add_entities(entities)


class TractiveSensor(TractiveEntity, SensorEntity):
    """Tractive sensor."""

    def __init__(self, user_id, trackable, tracker_details, unique_id, description):
        """Initialize sensor entity."""
        super().__init__(user_id, trackable, tracker_details)

        self._attr_unique_id = unique_id
        self._attr_device_info = self._device_info
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
        self._attr_native_value = event[self.entity_description.key]
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
