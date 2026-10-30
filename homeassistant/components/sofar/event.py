"""Support for Sofar event entities."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from itertools import takewhile
from typing import override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.fault_log import FaultLog
from sofar_modbus.modern.faults import FAULTS, FaultLogEntry

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util

from .const import LAST_HANDLED_FAULT
from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 0

ATTR_CATEGORY = "category"
ATTR_FAULT_ID = "fault_id"
ATTR_OCCURRED_AT = "occurred_at"

# A log entry as (fault id, inverter clock), free of any time zone.
type EntryKey = tuple[int, datetime]


@dataclass(frozen=True, kw_only=True)
class SofarEventEntityDescription(EventEntityDescription, SofarEntityDescription):
    """Describe a Sofar event entity."""

    fault_log_fn: Callable[[SofarInverter], FaultLog]


EVENT_DESCRIPTIONS: tuple[SofarEventEntityDescription, ...] = (
    SofarEventEntityDescription(
        key="fault",
        component="fault_log",
        translation_key="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_types=[fault.key for fault in FAULTS],
        fault_log_fn=lambda device: device.fault_log,
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
    # The newest entry handled; None while the log is empty.
    _handled: EntryKey | UndefinedType | None = UNDEFINED

    @override
    async def async_added_to_hass(self) -> None:
        """Resume after the entry handled before, or from the log as is."""
        if LAST_HANDLED_FAULT in (data := self.coordinator.config_entry.data):
            self._handled = (
                None
                if (stored := data[LAST_HANDLED_FAULT]) is None
                else (stored[0], datetime.fromisoformat(stored[1]))
            )
        elif self.available:
            self._remember(self._newest())
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
        if (handled := self._handled) is UNDEFINED:
            self._remember(self._newest())
            return
        for entry in reversed(
            list(
                takewhile(
                    lambda logged: _key(logged) != handled,
                    self._entries(),
                )
            )
        ):
            self._trigger_event(
                entry.fault.key,
                {
                    ATTR_FAULT_ID: entry.fault.id,
                    ATTR_CATEGORY: entry.fault.category.value,
                    ATTR_OCCURRED_AT: entry.occurred_at.replace(
                        tzinfo=dt_util.get_default_time_zone()
                    ).isoformat(),
                },
            )
            # One write per event, so each reaches state triggers.
            self.async_write_ha_state()
        if (newest := self._newest()) != handled:
            self._remember(newest)

    def _entries(self) -> tuple[FaultLogEntry, ...]:
        """Return the log entries, newest first."""
        return self.entity_description.fault_log_fn(self.coordinator.device).entries

    def _newest(self) -> EntryKey | None:
        """Return the newest entry the log holds now, if any."""
        return next((_key(entry) for entry in self._entries()), None)

    def _remember(self, handled: EntryKey | None) -> None:
        """Take the log as handled up to an entry, across restarts too."""
        self._handled = handled
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                LAST_HANDLED_FAULT: None
                if handled is None
                else [handled[0], handled[1].isoformat()],
            },
        )
