"""Support for Tractive binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CLIENT,
    DOMAIN,
    SERVER_UNAVAILABLE,
    TRACKABLES,
    TRACKER_HARDWARE_STATUS_UPDATED,
)
from .entity import TractiveEntity

TRACKERS_WITH_BUILTIN_BATTERY = ("TRNJA4", "TRAXL1")


class TractiveBinarySensor(TractiveEntity, BinarySensorEntity):
    """Tractive sensor."""

    def __init__(self, user_id, trackable, tracker_details, unique_id, description):
        """Initialize sensor entity."""
        super().__init__(user_id, trackable, tracker_details)

        self._attr_name = f"{trackable['details']['name']} {description.name}"
        self._attr_unique_id = unique_id
        self.entity_description = description

    @callback
    def handle_server_unavailable(self):
        """Handle server unavailable."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def handle_hardware_status_update(self, event):
        """Handle hardware status update."""
        self._attr_is_on = event[self.entity_description.key]
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


SENSOR_TYPE = BinarySensorEntityDescription(
    key=ATTR_BATTERY_CHARGING,
    name="Battery Charging",
    device_class=DEVICE_CLASS_BATTERY_CHARGING,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tractive device trackers."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    trackables = hass.data[DOMAIN][entry.entry_id][TRACKABLES]

    entities = []

    for item in trackables:
        if item.tracker_details["model_number"] not in TRACKERS_WITH_BUILTIN_BATTERY:
            continue
        entities.append(
            TractiveBinarySensor(
                client.user_id,
                item.trackable,
                item.tracker_details,
                f"{item.trackable['_id']}_{SENSOR_TYPE.key}",
                SENSOR_TYPE,
            )
        )

    async_add_entities(entities)
