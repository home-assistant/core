"""Sensor for Risco Events."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any

from pyrisco.cloud.event import Event

from homeassistant.components.binary_sensor import DOMAIN as BS_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import is_local
from .const import DOMAIN, EVENTS_COORDINATOR
from .coordinator import RiscoEventsDataUpdateCoordinator
from .entity import zone_unique_id

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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if is_local(config_entry):
        # no events in local comm
        return

    coordinator: RiscoEventsDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][EVENTS_COORDINATOR]
    sensors = [
        RiscoSensor(coordinator, category_id, [], name, config_entry.entry_id)
        for category_id, name in CATEGORIES.items()
    ]
    sensors.append(
        RiscoSensor(
            coordinator, None, CATEGORIES.keys(), "Other", config_entry.entry_id
        )
    )
    async_add_entities(sensors)


class RiscoSensor(CoordinatorEntity[RiscoEventsDataUpdateCoordinator], SensorEntity):
    """Sensor for Risco events."""

    _entity_registry: er.EntityRegistry

    def __init__(
        self,
        coordinator: RiscoEventsDataUpdateCoordinator,
        category_id: int | None,
        excludes: Collection[int],
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._event: Event | None = None
        self._category_id = category_id
        self._excludes = excludes
        self._name = name
        self._entry_id = entry_id
        self._attr_unique_id = f"events_{name}_{self.coordinator.risco.site_uuid}"
        self._attr_name = f"Risco {self.coordinator.risco.site_name} {name} Events"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._entity_registry = er.async_get(self.hass)

    def _handle_coordinator_update(self) -> None:
        events = self.coordinator.data
        for event in reversed(events):
            if event.category_id in self._excludes:
                continue
            if self._category_id is not None and event.category_id != self._category_id:
                continue

            self._event = event
            self.async_write_ha_state()

    @property
    def native_value(self) -> datetime | None:
        """Value of sensor."""
        if self._event is None:
            return None

        if res := dt_util.parse_datetime(self._event.time):
            return res.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes."""
        if self._event is None:
            return None

        attrs = {atr: getattr(self._event, atr, None) for atr in EVENT_ATTRIBUTES}
        if self._event.zone_id is not None:
            uid = zone_unique_id(self.coordinator.risco, self._event.zone_id)
            zone_entity_id = self._entity_registry.async_get_entity_id(
                BS_DOMAIN, DOMAIN, uid
            )
            if zone_entity_id is not None:
                attrs["zone_entity_id"] = zone_entity_id

        return attrs
