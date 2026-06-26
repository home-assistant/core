"""Sensor for Risco Events."""

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any, override

from pyrisco.cloud.event import Event

from homeassistant.components.binary_sensor import DOMAIN as BS_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import zone_unique_id
from .models import CloudData, RiscoConfigEntry

CATEGORIES = {
    2: "Alarm",
    4: "Status",
    7: "Trouble",
}
EVENT_ATTRIBUTES = [
    "category_id",
    "category_name",
    "type_id",
    "type_name",
    "name",
    "text",
    "partition_id",
    "zone_id",
    "user_id",
    "group",
    "priority",
    "raw",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RiscoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if not (cloud_data := config_entry.runtime_data.cloud_data):
        # no events in local comm
        return

    sensors = [
        RiscoSensor(cloud_data, category_id, [], name)
        for category_id, name in CATEGORIES.items()
    ]
    sensors.append(
        RiscoSensor(cloud_data, None, CATEGORIES.keys(), "Other")
    )
    async_add_entities(sensors)


class RiscoSensor(SensorEntity):
    """Sensor for Risco events."""

    _attr_should_poll = False
    _entity_registry: er.EntityRegistry

    def __init__(
        self,
        cloud_data: CloudData,
        category_id: int | None,
        excludes: Collection[int],
        name: str,
    ) -> None:
        """Initialize sensor."""
        self._cloud_data = cloud_data
        self._event: Event | None = None
        self._category_id = category_id
        self._excludes = excludes
        self._name = name
        self._attr_unique_id = f"events_{name}_{cloud_data.system.site_uuid}"
        self._attr_name = f"Risco {cloud_data.system.site_name} {name} Events"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to event updates."""
        self._entity_registry = er.async_get(self.hass)
        self.async_on_remove(
            self._cloud_data.system.add_event_handler(self._handle_events)
        )

    async def _handle_events(self, events: list[Event]) -> None:
        for event in events:  # newest first
            if event.category_id in self._excludes:
                continue
            if self._category_id is not None and event.category_id != self._category_id:
                continue
            self._event = event
            self.async_write_ha_state()
            return

    @property
    @override
    def native_value(self) -> datetime | None:
        """Value of sensor."""
        if self._event is None:
            return None

        if res := dt_util.parse_datetime(self._event.time):
            return res.replace(tzinfo=dt_util.get_default_time_zone())
        return None

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes."""
        if self._event is None:
            return None

        attrs = {atr: getattr(self._event, atr, None) for atr in EVENT_ATTRIBUTES}
        if self._event.zone_id is not None:
            uid = zone_unique_id(self._cloud_data.system, self._event.zone_id)
            zone_entity_id = self._entity_registry.async_get_entity_id(
                BS_DOMAIN, DOMAIN, uid
            )
            if zone_entity_id is not None:
                attrs["zone_entity_id"] = zone_entity_id

        return attrs
