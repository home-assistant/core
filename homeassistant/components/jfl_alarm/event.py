"""Contact ID events, as `event` entities.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**Panic changes no status byte at all.** There is nothing to poll for and nothing to hold a state:
the only trace a panic button leaves is a Contact ID event on the wire. That is the decisive
argument for the `event` domain over a sensor that briefly changes value — and it is why the events
travel on a dispatcher signal rather than in the coordinator snapshot. A snapshot is replayed to
every entity on every update and again after a restart, so an event stored in one would re-fire.

Home Assistant only lets an entity fire an event type it declared, so `event_types` comes from
`EventKind` — the classification the protocol package already assigns to every one of the 84 codes.
No `device_class` is set: the three the domain offers are `button`, `doorbell` and `motion`, and an
alarm event is none of them. Misusing one would give the wrong voice-assistant behaviour.

**The electric fence gets its own entity, and its own event types.** It reports the ordinary arm,
disarm and alarm codes with partition 99, so on 2026-08-08 the panel-wide entity read "Armed" when
the fence had been switched on from the mobile app and the house was never armed at all. Routing is
not enough to fix that — the panel-wide entity is meant to show everything — so `classify()` maps
partition 99 onto `fence_arm`, `fence_disarm` and `fence_alarm`, and the panel-wide entity now says
which it was.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pyjfl import EventKind, EventSubject, classify, lookup

from .const import CONF_SERIAL, SUBENTRY_TYPE_PANEL, signal_panel_event
from .entity import JflEntity, JflFenceEntity, JflPartitionEntity, async_add_discovered

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pyjfl import PanelEvent

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator, JflPanelState

PARALLEL_UPDATES = 0

EVENT_TYPES: list[str] = [kind.value for kind in EventKind]
"""Every classification the Contact ID table can produce. Declared up front because Home Assistant
refuses to fire a type an entity did not declare, and a refused event is a lost panic."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the panel-wide event entity now, and a per-partition one as partitions appear.

    The panel-wide entity is **not** discovered: it has nothing to read from the status frame, and
    the very first event a panel ever sends has to have somewhere to land. Waiting for a partition
    to prove it exists would drop that event, and the event most likely to arrive before anything
    else is a panic.
    """
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        async_add_entities(
            [JflPanelEventEntity(coordinator)], config_subentry_id=subentry.subentry_id
        )
        async_add_discovered(coordinator, async_add_entities, partial(_discover, coordinator))


@callback
def _discover(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return a per-partition event entity for each programmed partition, and one for the fence.

    Bookkeeping is kept separate from the alarm platform's: both discover partitions, and sharing
    one set would mean whichever ran first silently suppressed the other.
    """
    found: list[Entity] = []
    for index, partition in enumerate(state.partitions, start=1):
        if not partition.programmed or index in _created_partitions(coordinator):
            continue
        _created_partitions(coordinator).add(index)
        found.append(JflPartitionEventEntity(coordinator, index))

    if state.fence.present and not coordinator.discovered.fence_event:
        coordinator.discovered.fence_event = True
        found.append(JflFenceEventEntity(coordinator))
    return found


def _created_partitions(coordinator: JflPanelCoordinator) -> set[int]:
    """Return the partitions this platform has already created an event entity for."""
    return coordinator.discovered.event_partitions


_ORIGIN_SUBJECTS: Final = frozenset({"000", "099"})
"""Subject values that name **where a command came from**, not who issued it.

From the 2026-08-08 capture: `099` is the monitoring connection and `000` the mobile app.
Looking either up in the user list would put a real person's name on an event they had
nothing to do with, on any panel that happens to have a user with that number."""


class _JflEventBase(EventEntity):
    """Shared behaviour: subscribe to the panel's dispatcher signal and fire what matches."""

    _attr_event_types = EVENT_TYPES

    coordinator: JflPanelCoordinator

    async def async_added_to_hass(self) -> None:
        """Subscribe to this panel's events.

        The signal is scoped by config entry *and* serial, so two panels — or two config entries —
        never hear each other's events.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_panel_event(self.coordinator.config_entry.entry_id, self.coordinator.serial),
                self._handle_panel_event,
            )
        )

    @callback
    def _handle_panel_event(self, event: PanelEvent) -> None:
        if not self._wants(event):
            return
        code = lookup(event.code)
        payload: dict[str, Any] = {
            "code": event.code,
            "description": code.description,
            "partition": event.partition,
            "subject": event.subject,
            "subject_kind": code.subject.value,
            "is_fence": event.is_fence,
        }
        if name := self._subject_name(event, code.subject):
            payload["subject_name"] = name
        self._trigger_event(classify(event.code, event.partition).value, payload)
        self.async_write_ha_state()

    @callback
    def _subject_name(self, event: PanelEvent, kind: EventSubject) -> str:
        """Resolve the event's subject number to the name programmed in the panel.

        **"Who armed the house?" is the question this answers**, and until now the logbook could
        only say *003*. The same field carries a zone number for an alarm, so the resolution follows
        `code.subject` rather than guessing from the value.

        Only added to the payload when it resolves to something — before a programming read, and for
        a user or zone with no programmed name, the event carries `subject` alone exactly as before.
        That matches how the rest of the integration treats a name it does not have: a bare number
        already reads as "no name", and `Zone 3 (unnamed)` is noise on every dashboard row.

        ⚠️ **`000` and `099` are origins, not people.** The 2026-08-08 capture showed `099` is the
        monitoring connection — this integration itself — and `000` the mobile app, so neither is
        looked up: a panel with a user 99 would otherwise attribute every remote arm to them.
        A fence event carries user `099` for the same reason and is skipped with them.
        """
        if event.subject in _ORIGIN_SUBJECTS or event.is_fence:
            return ""
        try:
            number = int(event.subject)
        except ValueError:
            return ""
        programming = self.coordinator.programming
        if kind is EventSubject.USER:
            return programming.user_name(number)
        if kind is EventSubject.ZONE:
            return programming.zone_name(number)
        return ""

    @callback
    def _wants(self, event: PanelEvent) -> bool:
        """Whether this entity should fire for *event*. Overridden per partition."""
        raise NotImplementedError


class JflPanelEventEntity(JflEntity, _JflEventBase):
    """Every event the panel reports, whichever partition it came from."""

    _attr_translation_key = "panel_event"

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the panel-wide event entity."""
        super().__init__(coordinator, "event")

    @callback
    def _wants(self, event: PanelEvent) -> bool:
        return True


class JflPartitionEventEntity(JflPartitionEntity, _JflEventBase):
    """Events from one partition, so an automation can be scoped to an area of the house."""

    _attr_translation_key = "partition_event"

    def __init__(self, coordinator: JflPanelCoordinator, partition: int) -> None:
        """Create the event entity for *partition*, 1-based."""
        super().__init__(coordinator, partition, "event")

    @callback
    def _wants(self, event: PanelEvent) -> bool:
        """Match on the partition field, which the panel sends as two ASCII digits.

        Compared as an integer rather than as text: `"01"` and `"1"` have both been observed, and a
        string comparison would silently drop half of them. The fence reports partition 99, which no
        real partition can be, so it never lands here.
        """
        if event.is_fence:
            return False
        try:
            return int(event.partition) == self.partition
        except ValueError:
            return False


class JflFenceEventEntity(JflFenceEntity, _JflEventBase):
    """Events from the electric fence, on the fence's own sub-device.

    Without this, every fence arm, disarm and alarm arrives only on the panel-wide entity, mixed in
    with the house's own. An automation that wants "the fence was cut" would have to filter on an
    attribute; here it can subscribe to one entity.
    """

    _attr_translation_key = "fence_event"

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the fence event entity for this panel."""
        super().__init__(coordinator, "event")

    @callback
    def _wants(self, event: PanelEvent) -> bool:
        """Take the events the panel labels partition 99."""
        return event.is_fence
