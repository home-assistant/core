"""Support for Sofar event entities."""

from dataclasses import dataclass
from itertools import takewhile
from typing import override

from sofar_modbus.modern.faults import FAULTS, FaultLogEntry

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 0

ATTR_FAULT_ID = "fault_id"
ATTR_OCCURRED_AT = "occurred_at"

# A log entry as (fault id, occurred_at), the form the event stores.
type EntryKey = tuple[int, str]


@dataclass(frozen=True, kw_only=True)
class SofarEventEntityDescription(SofarEntityDescription, EventEntityDescription):
    """Describe a Sofar event entity."""


EVENT_DESCRIPTIONS: tuple[SofarEventEntityDescription, ...] = (
    SofarEventEntityDescription(
        key="fault",
        component="fault_log",
        translation_key="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=[fault.key for fault in FAULTS],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar event platform."""
    runtime_data = entry.runtime_data
    async_add_entities(
        SofarFaultEvent(runtime_data, description)
        for description in EVENT_DESCRIPTIONS
        if description.component in runtime_data.served_components
    )


def _occurred_at(entry: FaultLogEntry) -> str:
    """When the inverter logged the entry, in its local clock."""
    return entry.occurred_at.replace(tzinfo=dt_util.get_default_time_zone()).isoformat()


def _key(entry: FaultLogEntry) -> EntryKey:
    """Identify a log entry; simultaneous faults share a timestamp."""
    return entry.fault.id, _occurred_at(entry)


class SofarFaultEvent(SofarEntity, EventEntity):
    """Fires an event for each fault the inverter logs."""

    entity_description: SofarEventEntityDescription
    _known: set[EntryKey] | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Take the log as known up to the restored event."""
        await super().async_added_to_hass()
        if self.available:
            self._known = self._known_at_start()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire one event per log entry not seen before."""
        # A failed read says nothing about what the log holds.
        if self.available:
            known = self._known
            self._fire_new_entries(
                known if known is not None else self._known_at_start()
            )
        super()._handle_coordinator_update()

    def _known_at_start(self) -> set[EntryKey]:
        """Entries up to the restored event; all, without it in view."""
        keys = {_key(entry) for entry in self.coordinator.device.fault_log.entries}
        attributes = self.state_attributes
        restored = (attributes.get(ATTR_FAULT_ID), attributes.get(ATTR_OCCURRED_AT))
        return {restored} if restored in keys else keys

    def _fire_new_entries(self, known: set[EntryKey]) -> None:
        """Fire entries newer than the newest known one, oldest first."""
        entries = self.coordinator.device.fault_log.entries
        for entry in reversed(
            list(takewhile(lambda logged: _key(logged) not in known, entries))
        ):
            self._trigger_event(
                entry.fault.key,
                {
                    ATTR_FAULT_ID: entry.fault.id,
                    "category": entry.fault.category.value,
                    ATTR_OCCURRED_AT: _occurred_at(entry),
                },
            )
            # One write per event, so each reaches state triggers.
            self.async_write_ha_state()
        self._known = {_key(entry) for entry in entries}
