"""Support for ONVIF binary sensors."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.enum import try_parse_enum

from .const import DOMAIN
from .device import ONVIFDevice
from .entity import ONVIFBaseEntity
from .util import build_event_entity_names


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ONVIF sensor platform."""
    device: ONVIFDevice = hass.data[DOMAIN][config_entry.unique_id]

    events = device.events.get_platform("sensor")
    entity_names = build_event_entity_names(events)

    uids = set()
    entities = []
    for event in events:
        uids.add(event.uid)
        entities.append(ONVIFSensor(event.uid, device, name=entity_names[event.uid]))

    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if entry.domain == "sensor" and entry.unique_id not in uids:
            uids.add(entry.unique_id)
            entities.append(ONVIFSensor(entry.unique_id, device, entry=entry))

    async_add_entities(entities)
    uids_by_platform = device.events.get_uids_by_platform("sensor")

    @callback
    def async_check_entities() -> None:
        """Check if we have added an entity for the event."""
        nonlocal uids_by_platform
        if not (missing := uids_by_platform.difference(uids)):
            return

        events = device.events.get_platform("sensor")
        entity_names = build_event_entity_names(events)

        new_entities = [
            ONVIFSensor(uid, device, name=entity_names[uid]) for uid in missing
        ]
        if new_entities:
            uids.update(missing)
            async_add_entities(new_entities)

    device.events.async_add_listener(async_check_entities)


class ONVIFSensor(ONVIFBaseEntity, RestoreSensor):
    """Representation of a ONVIF sensor event."""

    _attr_should_poll = False

    def __init__(
        self,
        uid,
        device: ONVIFDevice,
        name: str | None = None,
        entry: er.RegistryEntry | None = None,
    ) -> None:
        """Initialize the ONVIF sensor."""
        self._attr_unique_id = uid
        if entry is not None:
            self._attr_device_class = try_parse_enum(
                SensorDeviceClass, entry.original_device_class
            )
            self._attr_entity_category = entry.entity_category
            self._attr_name = entry.name or entry.original_name
            self._attr_native_unit_of_measurement = entry.unit_of_measurement
        else:
            event = device.events.get_uid(uid)
            assert event
            assert name
            self._attr_device_class = try_parse_enum(
                SensorDeviceClass, event.device_class
            )
            self._attr_entity_category = event.entity_category
            self._attr_entity_registry_enabled_default = event.entity_enabled
            self._attr_name = f"{device.name} {name}"
            self._attr_native_unit_of_measurement = event.unit_of_measurement
            self._attr_native_value = event.value

        super().__init__(device)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        assert self._attr_unique_id is not None
        if (event := self.device.events.get_uid(self._attr_unique_id)) is not None:
            return event.value
        return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.device.events.async_add_listener(self.async_write_ha_state)
        )
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_sensor_data.native_value
