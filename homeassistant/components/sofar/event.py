"""Support for Sofar event entities."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from itertools import takewhile
from typing import override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.faults import FAULTS, FaultLogEntry

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription
from .helpers import StoredEntries, fault_log_store

PARALLEL_UPDATES = 0

ATTR_FAULT_ID = "fault_id"
ATTR_OCCURRED_AT = "occurred_at"

# A log entry as (fault id, inverter clock), free of any time zone.
type EntryKey = tuple[int, datetime]


@dataclass(frozen=True, kw_only=True)
class SofarEventEntityDescription(EventEntityDescription, SofarEntityDescription):
    """Describe a Sofar event entity."""

    entries_fn: Callable[[SofarInverter], tuple[FaultLogEntry, ...]]


EVENT_DESCRIPTIONS: tuple[SofarEventEntityDescription, ...] = (
    SofarEventEntityDescription(
        key="fault",
        component="fault_log",
        translation_key="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=[fault.key for fault in FAULTS],
        entries_fn=lambda device: device.fault_log.entries,
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


def _key(entry: FaultLogEntry) -> EntryKey:
    """Identify a log entry; simultaneous faults share a timestamp."""
    return entry.fault.id, entry.occurred_at


class SofarFaultEvent(SofarEntity, EventEntity):
    """Fires an event for each fault the inverter logs."""

    entity_description: SofarEventEntityDescription
    _known: set[EntryKey] | None = None
    _store: Store[StoredEntries]

    @override
    async def async_added_to_hass(self) -> None:
        """Resume from the entries handled before, or take all as known."""
        self._store = fault_log_store(self.hass, self.coordinator.config_entry.entry_id)
        # Before subscribing: an update during the load would mark all known.
        if (stored := await self._store.async_load()) is not None:
            self._known = {
                (fault_id, datetime.fromisoformat(occurred_at))
                for fault_id, occurred_at in stored
            }
        elif self.available:
            self._remember(self._logged())
        await super().async_added_to_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire entries newer than the newest known one, oldest first."""
        # Triggers skip a change from unavailable; recover first.
        super()._handle_coordinator_update()
        # A failed read says nothing about what the log holds.
        if not self.available:
            return
        # Automations arm their triggers only once Home Assistant runs.
        if self.hass.state is not CoreState.running:
            return
        if (known := self._known) is None:
            self._remember(self._logged())
            return
        for entry in reversed(
            list(
                takewhile(
                    lambda logged: _key(logged) not in known,
                    self._entries(),
                )
            )
        ):
            self._trigger_event(
                entry.fault.key,
                {
                    ATTR_FAULT_ID: entry.fault.id,
                    "category": entry.fault.category.value,
                    ATTR_OCCURRED_AT: entry.occurred_at.replace(
                        tzinfo=dt_util.get_default_time_zone()
                    ).isoformat(),
                },
            )
            # One write per event, so each reaches state triggers.
            self.async_write_ha_state()
        if (logged := self._logged()) != known:
            self._remember(logged)

    def _entries(self) -> tuple[FaultLogEntry, ...]:
        """Return the log entries, newest first."""
        return self.entity_description.entries_fn(self.coordinator.device)

    def _logged(self) -> set[EntryKey]:
        """Return every entry the log holds now."""
        return {_key(entry) for entry in self._entries()}

    def _remember(self, known: set[EntryKey]) -> None:
        """Take entries as handled, and keep them across restarts."""
        self._known = known
        self._store.async_delay_save(
            lambda: [(fault_id, at.isoformat()) for fault_id, at in known]
        )
