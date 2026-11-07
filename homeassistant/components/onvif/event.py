"""Support for ONVIF events."""

from typing import override

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .device import ONVIFConfigEntry, ONVIFDevice
from .entity import ONVIFBaseEntity
from .util import build_event_entity_names

EVENT_TYPE_TRIGGERED = "triggered"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ONVIFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ONVIF event platform."""
    device = config_entry.runtime_data

    events = device.events.get_platform("event")
    entity_names = build_event_entity_names(events)

    uids = set()
    entities = []
    for event in events:
        uids.add(event.uid)
        entities.append(ONVIFEvent(event.uid, device, name=entity_names[event.uid]))

    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if entry.domain == EVENT_DOMAIN and entry.unique_id not in uids:
            uids.add(entry.unique_id)
            entities.append(ONVIFEvent(entry.unique_id, device, entry=entry))

    async_add_entities(entities)
    uids_by_platform = device.events.get_uids_by_platform("event")

    @callback
    def async_check_entities() -> None:
        """Check if we have added an entity for the event."""
        nonlocal uids_by_platform
        if not (missing := uids_by_platform.difference(uids)):
            return

        events = device.events.get_platform("event")
        entity_names = build_event_entity_names(events)

        new_entities = [
            ONVIFEvent(uid, device, name=entity_names[uid]) for uid in missing
        ]
        if new_entities:
            uids.update(missing)
            async_add_entities(new_entities)

    device.events.async_add_listener(async_check_entities)


class ONVIFEvent(ONVIFBaseEntity, EventEntity):
    """Representation of a stateless ONVIF event."""

    _attr_should_poll = False
    _attr_event_types = [EVENT_TYPE_TRIGGERED]
    _attr_unique_id: str

    def __init__(
        self,
        uid: str,
        device: ONVIFDevice,
        name: str | None = None,
        entry: er.RegistryEntry | None = None,
    ) -> None:
        """Initialize the ONVIF event entity."""
        self._attr_unique_id = uid
        if entry is not None:
            self._attr_device_class = try_parse_enum(
                EventDeviceClass, entry.original_device_class
            )
            self._attr_entity_category = entry.entity_category
            self._attr_name = entry.name or entry.original_name
        else:
            event = device.events.get_uid(uid)
            assert event
            assert name
            self._attr_device_class = try_parse_enum(
                EventDeviceClass, event.device_class
            )
            self._attr_entity_category = event.entity_category
            self._attr_entity_registry_enabled_default = event.entity_enabled
            self._attr_name = f"{device.name} {name}"

        super().__init__(device)

    @callback
    def _async_handle_update(self) -> None:
        """Handle updated events from the event manager."""
        if not (
            triggers := self.device.events.async_pop_triggers(self._attr_unique_id)
        ):
            self.async_write_ha_state()
            return
        for _ in range(triggers):
            self._trigger_event(EVENT_TYPE_TRIGGERED)
            self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Connect to the event manager."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.device.events.async_add_listener(self._async_handle_update)
        )
        # Messages may have arrived before this entity was added
        self._async_handle_update()
