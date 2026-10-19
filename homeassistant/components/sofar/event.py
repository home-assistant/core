"""Support for Sofar event entities."""

from dataclasses import dataclass
from datetime import datetime
from itertools import takewhile
from typing import override

from sofar_modbus.modern.faults import FAULTS, FaultLogEntry

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 0

ATTR_FAULT_ID = "fault_id"
ATTR_OCCURRED_AT = "occurred_at"

STORAGE_VERSION = 1

# A log entry as (fault id, inverter clock), free of any time zone.
type EntryKey = tuple[int, datetime]
type StoredEntries = list[tuple[int, str]]


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


def fault_log_store(hass: HomeAssistant, entry_id: str) -> Store[StoredEntries]:
    """Return the store of the log entries an entry has handled."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.fault_log")


def _occurred_at(entry: FaultLogEntry) -> str:
    """When the inverter logged the entry, in its local clock."""
    return entry.occurred_at.replace(tzinfo=dt_util.get_default_time_zone()).isoformat()


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
        await super().async_added_to_hass()
        self._store = fault_log_store(self.hass, self.coordinator.config_entry.entry_id)
        if (stored := await self._store.async_load()) is not None:
            self._known = {
                (fault_id, datetime.fromisoformat(occurred_at))
                for fault_id, occurred_at in stored
            }
        elif self.available:
            self._remember(self._logged())

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire one event per log entry not seen before."""
        # Triggers skip a change from unavailable; recover first.
        super()._handle_coordinator_update()
        # A failed read says nothing about what the log holds.
        if self.available:
            if self._known is None:
                self._remember(self._logged())
            else:
                self._fire_new_entries(self._known)

    def _logged(self) -> set[EntryKey]:
        """Return every entry the log holds now."""
        return {_key(entry) for entry in self.coordinator.device.fault_log.entries}

    def _remember(self, known: set[EntryKey]) -> None:
        """Take entries as handled, and keep them across restarts."""
        self._known = known
        self._store.async_delay_save(
            lambda: [(fault_id, at.isoformat()) for fault_id, at in known]
        )

    def _fire_new_entries(self, known: set[EntryKey]) -> None:
        """Fire entries newer than the newest known one, oldest first."""
        for entry in reversed(
            list(
                takewhile(
                    lambda logged: _key(logged) not in known,
                    self.coordinator.device.fault_log.entries,
                )
            )
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
        if (logged := self._logged()) != known:
            self._remember(logged)
