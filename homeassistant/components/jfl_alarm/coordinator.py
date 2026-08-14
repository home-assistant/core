"""One coordinator per panel, fed by pushes from the listener.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

`DataUpdateCoordinator` is used with `update_interval=None`: nothing here polls on Home Assistant's
schedule. The listener pushes, and `async_set_updated_data` fans the new snapshot out. The panel
*is* polled for status, but that poll belongs to the connection, not to Home Assistant's update
loop — see pyjfl's `transport.py`.

Three decisions in this module are deliberate and easy to undo by accident:

* **`data` is never `None`.** It starts as an empty snapshot and `async_config_entry_first_refresh`
  is never called. A panel typically dials in ten to sixty seconds after Home Assistant starts, so
  a first refresh would fail the entry setup for a panel that is merely still booting.
* **Availability comes from the connection, not from `last_update_success`.** A coordinator that has
  never been updated is not a panel in trouble; a panel whose socket went away is.
* **Contact ID events do not go in the snapshot.** They go out on a dispatcher signal. A snapshot is
  replayed to every entity on every update and again after a restart, so an event kept in one would
  re-fire — a panic button that presses itself. Only the *timestamp* of the last event is state.

Sprint 3 added the command path, and it obeys three rules of its own:

* **Nothing is optimistic.** A command never writes a state. It schedules two status re-reads and
  the panel's own answer is what the entities show. The 2026-08-08 capture is the reason: arming
  returned a status frame that still showed zone 9 open, and the panel auto-bypassed it a second
  later.
* **Two gates, both of which must open.** `read_only` is the deliberate opt-in, in the panel's
  settings; the commands switch is the quick kill switch on the dashboard.
* **Permissions are checked at the moment of the call**, never cached into `supported_features`.
  `P-PART` is state-dependent — the same partition read `0x0B` disarmed and `0x1F` armed — so a
  feature set derived from it would make Home Assistant's buttons appear and disappear on their own.
"""

import asyncio
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from pyjfl import (
    EVENTS_PER_PAGE,
    UNKNOWN_MODEL,
    WIRELESS_PER_PAGE,
    ArmMode,
    CommandResponse,
    ConnectionInfo,
    EventRecord,
    FencePermissions,
    FenceState,
    GlobalZoneOptions,
    HolidayRecord,
    JflCapabilities,
    JflPanelLink,
    ModelSpec,
    Packet,
    PanelEvent,
    PanelNotConnectedError,
    PanelStatus,
    PartitionPermissions,
    PartitionRecord,
    PartitionState,
    PgmRecord,
    ProgrammingBlock,
    ReadRequest,
    TimerSettings,
    UnknownPacket,
    UserRecord,
    WirelessDevice,
    WirelessRecord,
    ZoneAlert,
    ZoneRecord,
    ZoneState,
    ZoneStatus,
    build_arm,
    build_arm_away,
    build_arm_stay,
    build_bypass_bitmap,
    build_disarm,
    build_fence_arm,
    build_fence_disarm,
    build_pgm_off,
    build_pgm_on,
    build_set_datetime,
    parse_auto_arm_time,
    parse_global_zone_options,
    parse_holidays,
    parse_partitions,
    parse_pgms,
    parse_timers,
    parse_users,
    parse_wireless,
    parse_zones,
    plan_region,
    zone_alert,
)

# `MAX_WIRELESS` and `REGIONS` are not re-exported from `pyjfl`'s top-level namespace (unlike
# `WIRELESS_PER_PAGE` above, which is and is imported from there). Reaching into
# `pyjfl.protocol.programming` for these two is a boundary compromise, tracked as a `pyjfl` library
# gap rather than fixed here — narrowing this import needs a release of `pyjfl` that exports them
# at the top level, which is out of this repository's control. See BACKLOG.md.
from pyjfl.protocol.programming import MAX_WIRELESS, REGIONS

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FENCE_PGM,
    DEFAULT_EVENT_LIMIT,
    DEFAULT_FENCE_PGM,
    DEFAULT_PROGRAMMING_READ_INTERVAL,
    DEFAULT_STATUS_INTERVAL,
    DOMAIN,
    LOGGER,
    NO_FENCE_PGM,
    PROGRAMMING_READ_FIRST_DELAY,
    PROGRAMMING_READ_GAP,
    PROGRAMMING_READ_IDLE_SLEEP,
    PROGRAMMING_READ_RETRIES,
    VERIFY_DELAYS,
    signal_panel_event,
)
from .device import async_apply_programmed_names, async_refresh_panel_device
from .repairs import async_check_model, async_report_lockout

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from homeassistant.config_entries import ConfigSubentry

    from . import JflConfigEntry


_ALERT_NIBBLES: Final[dict[ZoneAlert, ZoneStatus]] = {
    ZoneAlert.LOW_BATTERY: ZoneStatus.LOW_BATTERY,
    ZoneAlert.SUPERVISION: ZoneStatus.NOT_COMMUNICATING,
    ZoneAlert.TAMPER: ZoneStatus.TAMPER,
}
"""Which zone nibble reports the same condition each latched alert describes."""


@dataclass(frozen=True, slots=True)
class JflPanelState:
    """The snapshot every entity on one panel reads from.

    Empty is a legitimate value, and the one every panel starts in: the entry is set up before any
    panel has dialled in, and entities must exist and read as unavailable rather than not exist.
    """

    connection: ConnectionInfo | None = None
    status: PanelStatus | None = None
    available: bool = False

    connected_since: datetime | None = None
    """When the panel last dialled in — the start of the current session, or of the last one if it
    has since gone away. Survives a disconnect on purpose: "it last connected at 14:02" is exactly
    what you want to know at 15:00 when nothing is working."""

    last_seen_at: datetime | None = None
    """When **anything at all** was last heard from the panel: a status reply, a keep-alive, an
    event. This is the honest liveness signal — the connection can look open long after the panel
    has stopped talking, because a TCP socket does not notice a box that lost power."""

    last_event_at: datetime | None = None
    last_event_code: str | None = None
    unknown_packets: int = 0

    zone_alerts: Mapping[int, frozenset[ZoneAlert]] = field(default_factory=dict)
    """Per-zone conditions latched from Contact ID events, keyed by zone number.

    **This is state, not a stored event, and the distinction is the whole reason it is allowed
    here.** The module docstring forbids keeping events in the snapshot because a snapshot is
    replayed and an event would re-fire. "Zone 9's battery is low and has not been restored" does
    not re-fire when it is replayed — it is a fact that stays true until `3384` arrives.

    It exists because the zone nibble physically cannot hold it: one nibble, one value, so a
    low-battery sensor reports `6` when closed and `7` when somebody walks past it. See `ZoneAlert`.
    """

    @property
    def spec(self) -> ModelSpec:
        """The model's capability ceiling. Permissive, and never raises, for an unlisted byte.

        Before the panel has introduced itself there is no model byte at all, so the permissive
        fallback stands in — the same one an unlisted byte gets, for the same reason.
        """
        if self.connection is None:
            return UNKNOWN_MODEL
        return self.connection.spec

    @property
    def partitions(self) -> tuple[PartitionState, ...]:
        """Partition states, capped at what the model can have.

        The status frame always carries sixteen partition bytes regardless of the model, so a
        four-partition panel would otherwise offer twelve partitions that cannot exist.
        """
        if self.status is None:
            return ()
        return self.status.partitions[: self.spec.partitions]

    @property
    def zones(self) -> tuple[ZoneState, ...]:
        """Zone states, capped at what the model can have."""
        if self.status is None:
            return ()
        return self.status.zones[: self.spec.zones]

    @property
    def fence(self) -> FenceState:
        """The electric fence, from the status frame if there is one, else the connection frame."""
        if self.status is not None:
            return self.status.fence
        if self.connection is not None:
            return self.connection.fence
        return FenceState(0x00)

    def partition(self, number: int) -> PartitionState | None:
        """Return partition *number* (1-based), or `None` if this panel has no such partition."""
        partitions = self.partitions
        if 1 <= number <= len(partitions):
            return partitions[number - 1]
        return None

    def zone(self, number: int) -> ZoneState | None:
        """Return zone *number* (1-based), or `None` if this panel has no such zone."""
        for zone in self.zones:
            if zone.number == number:
                return zone
        return None

    def zone_alert(self, number: int, alert: ZoneAlert) -> bool:
        """Whether zone *number* is currently in *alert*, from **either** source.

        The nibble and the event latch are merged rather than one preferred over the other, because
        each sees something the other cannot: the nibble is present-tense but holds only one value,
        and the latch survives the nibble being overwritten but only exists if the panel reported
        the event to us. Either saying yes is a yes.
        """
        if alert in self.zone_alerts.get(number, frozenset()):
            return True
        zone = self.zone(number)
        return zone is not None and zone.status is _ALERT_NIBBLES[alert]


@dataclass(frozen=True, slots=True)
class JflProgramming:
    """What the panel's programming says about itself, once it has been read.

    Separate from `JflPanelState` on purpose. The status snapshot is replaced many times a minute;
    this changes only when somebody reprograms the panel, and the panel tells us when that happened
    through `KP`. Keeping them apart means a full read is not thrown away by the next status frame.

    ⚠️ **No user access codes are here, and none can be.** `UserRecord` carries `has_code` and the
    parser never returns the code itself — see pyjfl's `protocol/programming.py`. AGENTS.md §4.
    """

    checksum: bytes = b""
    """`KP` as it was when this was read. The panel changes it when, and only when, the programming
    changes, so comparing it against the status frame's is how this copy learns it is stale."""

    read_at: datetime | None = None
    zones: Mapping[int, ZoneRecord] = field(default_factory=dict)
    partitions: Mapping[int, PartitionRecord] = field(default_factory=dict)
    pgms: Mapping[int, PgmRecord] = field(default_factory=dict)
    users: Mapping[int, UserRecord] = field(default_factory=dict)
    wireless: Mapping[int, WirelessRecord] = field(default_factory=dict)
    """The enrolment table at `0x1800`, keyed by slot. A zone appearing here is wireless."""

    holidays: tuple[HolidayRecord, ...] = ()
    """The sixteen holiday slots, in order. Decoded 2026-08-09."""

    timers: TimerSettings | None = None
    """The panel's ten timers in real units, or `None` if the region did not come back.
    Decoded 2026-08-09 from a labelled differential — see pyjfl's `protocol/programming.py`."""

    zone_options: GlobalZoneOptions | None = None
    """The panel-wide zone options, which is where **zone doubling** lives — the flag that decides
    whether this panel really has 32 zones or 16. Decoded 2026-08-09."""

    auto_arm_time: tuple[int, int] | None = None
    """The first auto-arm schedule's `(hour, minute)`, or `None` when it is not set."""

    inventory: Mapping[int, WirelessDevice] = field(default_factory=dict)
    """The `0x59` inventory, keyed by **zone**, holding each radio detector's live condition.

    Separate from `wireless`, which is the enrolment *table* in the programming and says only that a
    zone has a radio device on it. This is what the panel currently knows about that device: signal
    quality, firmware, battery and when it last transmitted.

    It has to be asked for separately — `0x59` is its own command, not part of a programming read —
    and the panel's own UI leaves those columns blank until somebody presses *Atualizar*, which is
    the same thing happening.
    """

    incomplete: tuple[str, ...] = ()
    """Regions that did not come back. Named rather than counted, so "the zone names are missing"
    is answerable without re-reading anything."""

    @property
    def read(self) -> bool:
        """Whether a programming read has ever completed on this panel."""
        return self.read_at is not None

    def zone_name(self, number: int) -> str:
        """Return a zone's programmed name, or an empty string if it has none or is unknown.

        Empty rather than a placeholder: `docs/development/entity-map.md` settles that a zone with
        no name reads as its bare number, and never as `Zone 3 (unnamed)`.
        """
        record = self.zones.get(number)
        return record.name if record is not None else ""

    def partition_name(self, number: int) -> str:
        """Return a partition's programmed name, or an empty string."""
        record = self.partitions.get(number)
        return record.name if record is not None else ""

    def user_name(self, number: int) -> str:
        """Return a user's programmed name, or an empty string if unknown or unnamed.

        This is what turns *"armed by 003"* in the logbook into *"armed by Bruno"*. The name is all
        that is returned: `UserRecord` carries no access code, by construction — see `parse_users`.
        """
        record = self.users.get(number)
        return record.name if record is not None else ""

    def wireless_for_zone(self, number: int) -> WirelessRecord | None:
        """Return the wireless device enrolled on zone *number*, if there is one.

        A zone with no entry here is **hard-wired, or not enrolled** — the table only lists radio
        devices, which is precisely what makes it the answer to "is this zone wireless?".
        """
        return next(
            (
                record
                for record in self.wireless.values()
                if record.present and record.zone == number
            ),
            None,
        )


@dataclass(slots=True)
class _Discovery:
    """What the platforms have already created, so a re-run adds only what is new."""

    partitions: set[int] = field(default_factory=set)
    zones: set[int] = field(default_factory=set)
    timers: bool = False
    """The panel's timer sensors, which exist only after a programming read."""

    wireless_zones: set[int] = field(default_factory=set)
    """Zones that already have their radio-detector entities. Kept apart from `zones` because these
    appear only after a programming read, long after the zone itself."""

    event_partitions: set[int] = field(default_factory=set)
    """Kept apart from `partitions`: two platforms discover partitions, and sharing one set would
    mean whichever ran first silently suppressed the other."""

    fence: bool = False
    """The fence switch, on the `switch` platform.

    Four platforms create something for the fence, and each keeps its own flag for the same reason
    the partitions do: one shared flag means whichever platform is set up first silently suppresses
    the other three.
    """

    fence_alarm: bool = False
    """The fence's `safety` binary sensor."""

    fence_state: bool = False
    """The fence's enumerated state sensor."""

    fence_event: bool = False

    pgms: set[int] = field(default_factory=set)
    bypass: set[int] = field(default_factory=set)


class JflPanelCoordinator(DataUpdateCoordinator[JflPanelState]):
    """Holds one panel's state and pushes it at the entities.

    One of these exists per panel subentry, whether or not the panel has ever connected.
    """

    config_entry: JflConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: JflConfigEntry,
        subentry: ConfigSubentry,
        link: JflPanelLink,
        *,
        status_interval: int = DEFAULT_STATUS_INTERVAL,
        programming_read_interval: int = DEFAULT_PROGRAMMING_READ_INTERVAL,
        read_only: bool = True,
    ) -> None:
        """Bind a coordinator to one panel's link on the shared listener."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {link.serial}",
            # Nothing polls on Home Assistant's schedule. The panel pushes and we poll it ourselves
            # on the connection's own task, which knows whether there is a socket to poll over.
            update_interval=None,
            # The snapshot is a frozen dataclass, so identical content really is identical and
            # entities can be spared a write for a poll that changed nothing.
            always_update=False,
        )
        self.link = link
        self.subentry = subentry
        self.serial = link.serial
        self.status_interval = status_interval
        self.programming_read_interval = programming_read_interval
        self.read_only = read_only
        self.discovered = _Discovery()

        self.programming = JflProgramming()
        """What the panel's programming says, once `async_read_programming` has run.

        Deliberately **not** part of the coordinator snapshot: it changes when somebody reprograms
        the panel, not several times a minute, and putting it in the snapshot would mean a full read
        is discarded by the next status frame."""

        self._programming_lock = asyncio.Lock()

        self._programming_unreadable = False
        """Set when the automatic read found a panel that will not answer `0x44`.

        ADR-0010's requirement, and the reason the automatic read is safe to add at all: a panel
        that does not implement the programming commands must be asked **once** and then left alone,
        not hammered with thirty requests on every reconnection. The manual button and the service
        still work — a person asking explicitly is not a loop."""

        self.commands_enabled = True
        """The master switch's position. Owned by the switch entity, which restores it on start.

        `True` here is not a relaxation: `read_only` defaults to on, and **both** gates have to
        open. Defaulting this one to off would mean a user who deliberately turned `read_only` off
        still found nothing worked, with no clue why.
        """

        self.auth_blocked = False
        """Set by a `0xA1` or `0xAA` reply, and never cleared on its own. See `_handle_packet`."""

        self._unsubscribe: list[Callable[[], None]] = []
        self._poll_task: asyncio.Task[None] | None = None
        self._programming_task: asyncio.Task[None] | None = None
        self._warned_unavailable = False
        # `data` must never be None: entities are added before any panel has dialled in.
        self.async_set_updated_data(JflPanelState())

    # --- capabilities ---------------------------------------------------------------------------

    @property
    def capabilities(self) -> JflCapabilities:
        """What this panel can do, merged from the model, the status frame and the programming.

        The single place the three sources are combined — see pyjfl's `protocol/capabilities.py`.
        It is rebuilt on demand rather than cached because two of its three inputs change: the
        status frame arrives after the entities do, and the programming only after an explicit
        read. The merge is cheap, and a stale capability is worse than recomputing one.
        """
        return JflCapabilities.detect(
            self.data.spec,
            self.data.status,
            self.programming.pgms,
            self.programming.zone_options,
        )

    @property
    def pgm_functions_known(self) -> bool:
        """Whether what each PGM output *does* has been settled, one way or the other.

        `True` once a programming read has completed, and also once the panel has proved it will
        not answer `0x44` at all — in which case the answer is "nothing is known, and nothing ever
        will be", which is just as final and must not hold the entities back for ever.

        **The switch platform waits for this before creating the PGM switches**, because a PGM's
        function decides which device its switch belongs to, whether it is a control or a
        configuration entity, and whether it is created enabled — and all three are registry
        properties Home Assistant fixes when the entity is registered and never revisits. Creating
        the switches on the first status frame, as Sprint 4 did, meant deciding all three before the
        only source that can answer had spoken. See `switch._discover_pgms`.
        """
        return self.programming.read or self._programming_unreadable

    @property
    def configured_fence_pgm(self) -> int:
        """The PGM the user named as the fence's power in the panel's settings, or `0` for none.

        The override half of `JflCapabilities.effective_fence_pgm`: a value here wins over what a
        programming read detects, because the user may know something the programming does not.
        """
        return int(
            self.subentry.data.get(CONF_FENCE_PGM, DEFAULT_FENCE_PGM) or NO_FENCE_PGM
        )

    # --- lifecycle ------------------------------------------------------------------------------

    async def async_setup_panel(self) -> None:
        """Subscribe to the link and start polling. Never fails on a panel that is not there."""
        self._unsubscribe.append(
            self.link.async_add_packet_listener(self._handle_packet)
        )
        self._unsubscribe.append(
            self.link.async_add_availability_listener(self._handle_available)
        )
        self._poll_task = self.config_entry.async_create_background_task(
            self.hass, self._poll_forever(), name=f"{DOMAIN} poll {self.serial}"
        )
        self._programming_task = self.config_entry.async_create_background_task(
            self.hass,
            self._read_programming_forever(),
            name=f"{DOMAIN} programming {self.serial}",
        )
        if self.link.connected:
            # The panel was already talking to a previous config entry load, or dialled in between
            # the listener starting and the platforms being forwarded.
            self._handle_available(True)

    async def async_shutdown_panel(self) -> None:
        """Unsubscribe and stop polling."""
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self._unsubscribe.clear()
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
        if self._programming_task is not None:
            self._programming_task.cancel()
            self._programming_task = None

    # --- the poll loop --------------------------------------------------------------------------

    async def _poll_forever(self) -> None:
        """Ask the panel for a status frame on a fixed interval, forever.

        The panel never volunteers its status — `0x4D` has to be asked for. This is a *read*, so it
        runs in read-only mode too; without it there would be no zone or partition state at all.
        """
        while True:
            await asyncio.sleep(self.status_interval)
            if not self.link.connected:
                continue
            try:
                await self.link.async_request_status()
            except PanelNotConnectedError:
                # A race with a disconnect. The availability listener has already dealt with it.
                LOGGER.debug("%s: status poll skipped, panel disconnected", self.serial)
            except OSError as err:
                LOGGER.debug("%s: status poll failed: %s", self.serial, err)

    async def _read_programming_forever(self) -> None:
        """Read the programming once when the panel appears, then on the configured interval.

        Three rules, each of which exists because of a specific way this could go wrong.

        **Once per panel, always.** The first read happens whatever the interval is set to,
        including `0`. It is what makes a freshly added panel show *Zona 3 Cozinha* instead of
        *Zone 3* without anybody knowing there is a button.

        **Once is also the probe.** If the first read comes back with nothing, the panel does not
        answer `0x44` and is never asked again automatically — ADR-0010's condition for making the
        read implicit.

        **A periodic read that changes nothing costs one comparison.** `KP` is in every status
        frame and changes only when the programming does, so the interval tick re-reads only when
        the panel says something moved. On an unchanged panel this loop is silent for ever.
        """
        while True:
            await asyncio.sleep(PROGRAMMING_READ_FIRST_DELAY)
            if not self.link.connected or self._programming_unreadable:
                continue
            if self.programming.read and not self._programming_changed():
                await asyncio.sleep(self._programming_sleep())
                continue
            if self.programming.read and self.programming_read_interval <= 0:
                # Read once already, and the repeat is switched off.
                await asyncio.sleep(self._programming_sleep())
                continue
            try:
                result = await self.async_read_programming()
            except (PanelNotConnectedError, OSError) as err:
                LOGGER.debug(
                    "%s: automatic programming read failed: %s", self.serial, err
                )
                await asyncio.sleep(self._programming_sleep())
                continue
            if not result.zones and not result.partitions:
                self._programming_unreadable = True
                LOGGER.warning(
                    "Panel %s did not answer the programming read, so its zones and partitions "
                    "will keep their generic names. It will not be asked again automatically; "
                    "the 'Read programming' button still works",
                    self.serial,
                )
            await asyncio.sleep(self._programming_sleep())

    def _programming_sleep(self) -> float:
        """How long until the next tick — the interval, or a long idle wait when it is off."""
        if self.programming_read_interval <= 0:
            return PROGRAMMING_READ_IDLE_SLEEP
        return self.programming_read_interval * 60

    def _programming_changed(self) -> bool:
        """Whether `KP` says the panel's programming moved since the last read.

        `True` when either value is missing: an unknown answer must not be read as "unchanged", or
        a panel whose status has not arrived yet would never be read at all.
        """
        status = self.data.status
        if status is None or not self.programming.checksum:
            return True
        return bool(status.programming_checksum != self.programming.checksum)

    async def async_refresh_status(self) -> None:
        """Ask for a status frame now. Raises if the panel is not connected."""
        LOGGER.debug("%s: status refresh requested", self.serial)
        await self.link.async_request_status()

    # --- reading the programming ------------------------------------------------------------------

    async def async_read_programming(self) -> JflProgramming:
        """Read the panel's programming into a structured snapshot.

        **A read, not a command**, so it runs in `read_only` mode and passes neither gate — the same
        reasoning that keeps the status poll running. Sprint 6 implements no write path at all.

        Paced rather than fired at once: this is thirty-odd round trips on a link that is also
        carrying the status poll and, on a Bus panel, the keypad bus. A region that fails is named
        in `incomplete` and the rest is kept — thirty-one zone names are worth having when zone
        32's request went astray.

        Only one read runs at a time. A second caller waits for the first rather than doubling the
        traffic, which matters because both the entity layer and the diagnostics download want this.
        """
        async with self._programming_lock:
            LOGGER.debug("%s: reading the programming", self.serial)
            blocks: dict[str, bytes] = {}
            missing: list[str] = []
            checksum = b""

            for region in REGIONS:
                data, region_checksum = await self._async_read_region(region)
                if data is None:
                    missing.append(region)
                    continue
                blocks[region] = data
                checksum = region_checksum or checksum

            programming = self._build_programming(blocks, checksum, tuple(missing))
            programming = replace(
                programming, inventory=await self._async_read_inventory()
            )
            self.programming = programming
            LOGGER.debug(
                "%s: programming read — %d zones, %d partitions, %d wireless devices%s",
                self.serial,
                len(programming.zones),
                len(programming.partitions),
                sum(1 for record in programming.wireless.values() if record.present),
                f", missing {', '.join(missing)}" if missing else "",
            )
            async_apply_programmed_names(
                self.hass,
                entry_id=self.config_entry.entry_id,
                subentry_id=self.subentry.subentry_id,
                serial=self.serial,
                zones={
                    number: record.name for number, record in programming.zones.items()
                },
                partitions={
                    number: record.name
                    for number, record in programming.partitions.items()
                },
                wireless={
                    record.zone: record
                    for record in programming.wireless.values()
                    if record.present
                },
            )
            # Entities read names from `self.programming`, which is not part of the snapshot, so
            # they have to be told to look again.
            self.async_update_listeners()
            return programming

    async def async_read_events(
        self, *, since: int = 0, limit: int = DEFAULT_EVENT_LIMIT
    ) -> list[EventRecord]:
        """Page through the panel's own event memory (`0x48`), forward from *since*.

        **A read, like the programming read**, so it works in `read_only` mode and passes neither
        command gate. It is the only place the panel's *history* lives: the status frame is the
        present tense and the `0x24` stream is live-only.

        ⚠️ **These records are never fired at the `event` entities, and that is deliberate.** An
        `event` entity firing is a live occurrence: automations run, notifications go out, and a
        replayed `1120` is a panic button pressing itself at three in the morning. The same
        reasoning keeps events out of the coordinator snapshot — see the module docstring. What this
        returns is *data*, for a service response, and nothing here writes an entity state.

        **Paging is forward only, oldest first**, because that is what the panel offers: there is no
        request for "the last twenty". So *limit* is a hard stop rather than a nicety — the author's
        panel held 1073 records, which is 135 round trips on a link that is also carrying the status
        poll. A caller wanting the tail keeps the highest `serial` it saw and passes it as *since*
        next time.

        Stops at the first page that returns nothing, that returns fewer than a full page, or that
        does not advance the cursor — the last of which is the guard that matters, because a panel
        answering with the same page forever would otherwise loop until *limit*.
        """
        collected: list[EventRecord] = []
        cursor = max(0, since)
        while len(collected) < limit:
            try:
                page = await self.link.async_read_events(cursor)
            except (PanelNotConnectedError, OSError, TimeoutError) as err:
                # The same treatment the wireless inventory gets: a panel that does not implement
                # `0x48`, or that stops answering half way, returns what was read rather than
                # raising. Partial history is worth having; a traceback in a service call is not.
                LOGGER.debug(
                    "%s: event buffer read stopped at %d: %s", self.serial, cursor, err
                )
                break
            fresh = [record for record in page.records if record.serial > cursor]
            if not fresh:
                break
            collected.extend(fresh)
            cursor = max(record.serial for record in fresh)
            if len(page.records) < EVENTS_PER_PAGE:
                break
        LOGGER.debug(
            "%s: read %d buffered events, up to serial %d",
            self.serial,
            len(collected),
            cursor,
        )
        return collected[:limit]

    async def _async_read_region(self, region: str) -> tuple[bytes | None, bytes]:
        """Read one named region, returning its bytes and the `KP` the panel reported with them."""
        assembled = bytearray()
        checksum = b""
        for request in plan_region(region):
            block = await self._async_read_block(request)
            if block is None:
                return None, checksum
            assembled += block.data
            checksum = block.checksum
            await asyncio.sleep(PROGRAMMING_READ_GAP)
        return bytes(assembled), checksum

    async def _async_read_block(self, request: ReadRequest) -> ProgrammingBlock | None:
        """Read one block, retrying briefly. `None` when it never arrives."""
        for attempt in range(PROGRAMMING_READ_RETRIES):
            try:
                return await self.link.async_read_programming(
                    request.address, request.count
                )
            except (PanelNotConnectedError, OSError, TimeoutError) as err:
                LOGGER.debug(
                    "%s: programming read of %#06x+%d failed (attempt %d): %s",
                    self.serial,
                    request.address,
                    request.count,
                    attempt + 1,
                    err,
                )
        return None

    async def _async_read_inventory(self) -> dict[int, WirelessDevice]:
        """Read the `0x59` wireless inventory, page by page, keyed by zone.

        **Failure here is not failure of the programming read.** The inventory is extra information
        about radio detectors; a panel with none, or one that does not implement `0x59` at all,
        must still get its zone and partition names. So every error is swallowed to `debug` and the
        result is simply empty.

        Paging stops at the first page that returns nothing, rather than always asking for all four:
        a panel with nine devices has one page of eight and one of one, and there is no reason to
        ask about slots 17-32 that cannot exist.

        ⚠️ **Pages are numbered from zero**, which is what ActiveNet does (`59 08 00`, then
        `59 08 01`). Starting at one silently skips the first eight devices and returns only the
        stragglers — it looked like a panel with one wireless sensor instead of nine.
        """
        devices: dict[int, WirelessDevice] = {}
        for page in range(MAX_WIRELESS // WIRELESS_PER_PAGE):
            try:
                inventory = await self.link.async_read_wireless(page)
            except (PanelNotConnectedError, OSError, TimeoutError) as err:
                LOGGER.debug(
                    "%s: wireless inventory page %d failed: %s", self.serial, page, err
                )
                break
            present = [
                device
                for device in inventory.devices
                if device.serial not in (0, 0xFFFFFFFF)
            ]
            if not present:
                break
            for device in present:
                devices[device.zone] = device
            await asyncio.sleep(PROGRAMMING_READ_GAP)
        if devices:
            LOGGER.debug(
                "%s: wireless inventory — %d devices", self.serial, len(devices)
            )
        return devices

    @callback
    def _build_programming(
        self, blocks: Mapping[str, bytes], checksum: bytes, missing: tuple[str, ...]
    ) -> JflProgramming:
        """Turn the raw regions into typed records, keyed by their own numbers."""
        return JflProgramming(
            checksum=checksum,
            read_at=dt_util.utcnow(),
            zones=self._records(blocks, "zones", parse_zones),
            partitions=self._records(blocks, "partition_names", parse_partitions),
            pgms=self._records(blocks, "pgms", parse_pgms),
            # Parsed and kept for the name and the "is a code set?" flag. The code itself never
            # leaves `parse_users`, so nothing downstream — diagnostics included — can leak one.
            users=self._records(blocks, "users", parse_users),
            wireless={
                record.slot: record
                for record in parse_wireless(
                    blocks.get("wireless", b""), REGIONS["wireless"][0]
                )
            },
            holidays=tuple(
                parse_holidays(blocks.get("holidays", b""), REGIONS["holidays"][0])
            ),
            timers=parse_timers(blocks.get("timers", b""), REGIONS["timers"][0]),
            zone_options=parse_global_zone_options(
                blocks.get("zone_options", b""), REGIONS["zone_options"][0]
            ),
            auto_arm_time=parse_auto_arm_time(
                blocks.get("timers", b""), REGIONS["timers"][0]
            ),
            incomplete=missing,
        )

    @staticmethod
    def _records(
        blocks: Mapping[str, bytes],
        region: str,
        parse: Callable[[bytes, int], list[Any]],
    ) -> dict[int, Any]:
        """Run one region's parser and key the result by record number."""
        data = blocks.get(region)
        if data is None:
            return {}
        return {record.number: record for record in parse(data, REGIONS[region][0])}

    # --- outgoing commands ----------------------------------------------------------------------

    async def async_arm(self, partition: int, mode: ArmMode) -> None:
        """Arm *partition* (1-based) in *mode*. Source: `docs/protocol/commands.md`.

        The three modes are three different commands, not three names for one — see `ArmMode`. The
        permission bit checked is the one for the mode actually being used, so a panel with no STAY
        programmed says so instead of appearing to accept a command it will drop.
        """
        permissions = self._partition_permissions(partition)
        builder, permitted, bit = {
            ArmMode.TOTAL: (build_arm, permissions.may_arm, "TECLA3 (arm)"),
            ArmMode.STAY: (build_arm_stay, permissions.may_arm_stay, "TECLA5 (stay)"),
            ArmMode.AWAY: (build_arm_away, permissions.may_arm_away, "TECLA6 (away)"),
        }[mode]
        self._require_permission(permitted, bit)
        LOGGER.debug("%s: arming partition %d, mode %s", self.serial, partition, mode)
        await self._async_command(lambda seq: builder(seq, partition))

    async def async_disarm(self, partition: int) -> None:
        """Disarm *partition*, 1-based.

        Idempotent at the panel: disarming a partition that is already disarmed changes nothing and
        sounds nothing, which is what makes it safe to call from an automation that cannot know.
        """
        self._require_permission(
            self._partition_permissions(partition).may_disarm, "TECLA4 (disarm)"
        )
        LOGGER.debug("%s: disarming partition %d", self.serial, partition)
        await self._async_command(lambda seq: build_disarm(seq, partition))

    async def async_fence(self, *, arm: bool) -> None:
        """Arm or disarm the electric fence — the project's primary goal.

        Path A, the unauthenticated one, and **only** path A. The 2026-08-08 capture proved it works
        on the real panel (`7B 06 1A 4E 63 4A` armed it, `7B 06 22 4F 63 73` disarmed it), and it
        carries no password and therefore no lockout risk at all. The authenticated `0x37` fallback
        the sprint plan allowed for is deliberately not wired up: it would need a panel user code,
        and five wrong ones block remote operation until someone walks to the keypad. AGENTS.md §6.
        """
        permissions = self._fence_permissions()
        self._require_permission(
            permissions.may_arm if arm else permissions.may_disarm,
            "300 TECLA3/TECLA4, and 'Opera eletrificador' at 301-398",
        )
        LOGGER.debug(
            "%s: %s the electric fence", self.serial, "arming" if arm else "disarming"
        )
        await self._async_command(build_fence_arm if arm else build_fence_disarm)

    async def async_pgm(self, number: int, *, on: bool) -> None:
        """Switch PGM *number* (1-based) on or off. Source: `docs/protocol/pgm-and-bypass.md`.

        ⚠️ The caller is responsible for not handing this the PGM that drives the electric fence.
        The guard lives in the switch platform, where the panel's configured `fence_pgm` is known;
        the coordinator deliberately does not second-guess a deliberate call.
        """
        self._require_pgm_permission(number)
        LOGGER.debug(
            "%s: switching PGM %d %s", self.serial, number, "on" if on else "off"
        )
        builder = build_pgm_on if on else build_pgm_off
        await self._async_command(lambda seq: builder(seq, number))

    async def async_bypass(self, zone: int, *, bypassed: bool) -> None:
        """Bypass or un-bypass one *zone*, leaving every other zone's bypass exactly as it is.

        **`0x52` replaces the whole bitmap**, so this is a read-modify-write — and what it reads is
        the panel's own current answer (`bypassed_zones`, from the zone nibbles in the last status
        frame), never a set this integration remembered. A remembered set would silently un-bypass
        a zone somebody inhibited at the keypad.
        """
        status = self.data.status
        if status is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_status_yet",
                translation_placeholders={"serial": self.serial},
            )
        zone_state = self.data.zone(zone)
        if zone_state is not None and not zone_state.may_bypass:
            # `P-INIB` says the panel will not inhibit this zone. Unlike the arm permissions this is
            # a programming choice rather than a state, but it is checked the same way and at the
            # same moment, so the message can name the address.
            self._require_permission(False, "the zone's 'permite inibir' attribute")

        wanted = set(status.bypassed_zones)
        wanted.add(zone) if bypassed else wanted.discard(zone)
        LOGGER.debug(
            "%s: %s zone %d; bypass set becomes %s",
            self.serial,
            "bypassing" if bypassed else "un-bypassing",
            zone,
            sorted(wanted),
        )
        await self.async_set_bypass_mask(frozenset(wanted))

    async def async_set_bypass_mask(self, zones: frozenset[int]) -> None:
        """Replace the whole manual-bypass bitmap with exactly *zones*.

        The advanced form, and the shape the command really has. `async_bypass` is what an entity
        should call; this is for the service, and for clearing everything with an empty set.
        """
        LOGGER.debug("%s: setting the bypass bitmap to %s", self.serial, sorted(zones))
        await self._async_command(lambda seq: build_bypass_bitmap(seq, zones))

    async def async_sync_time(self, now: datetime) -> None:
        """Set the panel clock from *now*, which the caller has already made local.

        Worth doing because the panel timestamps every event it reports from its own clock: a panel
        that has drifted files today's alarm under yesterday afternoon.
        """
        LOGGER.debug("%s: setting the panel clock to %s", self.serial, now.isoformat())
        await self._async_command(
            lambda seq: build_set_datetime(
                seq,
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                day=now.day,
                month=now.month,
                year=now.year,
            )
        )

    async def _async_command(self, builder: Callable[[int], bytes]) -> None:
        """Send one command, if both gates allow it, and verify it afterwards.

        **Nothing is written to the snapshot here.** The panel answers a command with a status
        frame, but that frame is not the final truth: arming partition 1 in the capture returned a
        status still showing zone 9 open, and the panel auto-bypassed it a second later. So the
        state comes from the two scheduled re-reads, and from the ordinary poll after that.
        """
        self._require_writable()
        try:
            await self.link.async_send_command(builder)
        except PanelNotConnectedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="panel_not_connected",
                translation_placeholders={"serial": self.serial},
            ) from err
        self._schedule_verification()

    @callback
    def _schedule_verification(self) -> None:
        """Re-read the status shortly after a command, twice.

        Once at 600 ms, which catches the command taking effect, and again at 2 s, which catches
        what the panel decided on its own afterwards — an auto-bypass, an exit delay starting, a
        zone that was open closing.
        """

        async def _verify(_now: datetime) -> None:
            try:
                await self.link.async_request_status()
            except (PanelNotConnectedError, OSError) as err:
                LOGGER.debug(
                    "%s: post-command status re-read failed: %s", self.serial, err
                )

        for delay in VERIFY_DELAYS:
            self.config_entry.async_on_unload(
                async_call_later(self.hass, delay, _verify)
            )

    # --- guards ---------------------------------------------------------------------------------

    def _require_writable(self) -> None:
        """Refuse to send anything unless both gates are open, and say which one is shut."""
        if self.read_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="read_only",
                translation_placeholders={"serial": self.serial},
            )
        if not self.commands_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="commands_disabled",
                translation_placeholders={"serial": self.serial},
            )

    def _require_permission(self, permitted: bool, address: str) -> None:
        """Refuse a command the panel has not granted, naming the address the installer must check.

        The panel answers a refused path-A command with an ordinary status frame and no error at
        all, so without this the user sees a button that does nothing and no explanation anywhere.
        """
        if not permitted:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_permitted",
                translation_placeholders={"serial": self.serial, "address": address},
            )

    def _require_pgm_permission(self, number: int) -> None:
        """Refuse a PGM the panel will not operate, naming the address that decides it.

        `P-PGM` is clear both for a PGM that is not programmed and for one whose function is not
        user-operable — only functions **12** (with retention) and **13** (without) are — and the
        panel answers either with `0xA9` on the authenticated path and with silence on this one. The
        address to look at is the same in both cases.
        """
        status = self.data.status
        if status is None:
            return
        self._require_permission(
            status.pgm_permitted(number), "821-824 (the PGM's function)"
        )

    def _partition_permissions(self, partition: int) -> PartitionPermissions:
        """`P-PART[i]` for *partition*, read at the moment of the call.

        Never cached into `supported_features`: the same partition read `0x0B` while disarmed and
        `0x1F` while armed, so a cached copy would make buttons come and go. Before the first status
        frame there is nothing to check against, and a permissive default is right — the panel is
        the authority, and refusing on our own guess would block a command the panel would accept.
        """
        status = self.data.status
        if status is None or not 1 <= partition <= len(status.partition_permissions):
            return PartitionPermissions(0xFF)
        return status.partition_permissions[partition - 1]

    def _fence_permissions(self) -> FencePermissions:
        """`P-ELET`, read at the moment of the call. Permissive before the first status frame."""
        status = self.data.status
        if status is None:
            return FencePermissions(0xFF)
        return status.fence_permissions

    # --- incoming -------------------------------------------------------------------------------

    @callback
    def _handle_packet(self, packet: Packet) -> None:
        """Fold one decoded packet into the snapshot, or dispatch it if it is an event.

        **Every** packet stamps `last_seen_at`, including the keep-alive that carries no data at
        all. A keep-alive is not interesting for its content — it is interesting because it proves
        the panel is still there, and that is precisely what the timestamp records.
        """
        now = dt_util.utcnow()
        state = replace(self.data, last_seen_at=now, available=True)

        if isinstance(packet, ConnectionInfo):
            async_check_model(self.hass, packet)
            # The device registry has to be told explicitly. Home Assistant reads an entity's
            # `device_info` once, when the entity is added — and every entity here was added before
            # this frame arrived, back when the model was still the "unknown" fallback.
            async_refresh_panel_device(
                self.hass,
                entry_id=self.config_entry.entry_id,
                subentry_id=self.subentry.subentry_id,
                info=packet,
                name=self.subentry.title,
            )
            self.async_set_updated_data(
                replace(state, connection=packet, connected_since=now)
            )
            return
        if isinstance(packet, PanelStatus):
            self.async_set_updated_data(replace(state, status=packet))
            return
        if isinstance(packet, PanelEvent):
            self._handle_event(packet, state, now)
            return
        if isinstance(packet, CommandResponse):
            self._handle_command_response(packet)
        if isinstance(packet, UnknownPacket):
            # Counted rather than dropped: an undocumented command shows up here first.
            LOGGER.debug(
                "%s: undecoded command 0x%02X, payload %s",
                self.serial,
                packet.cmd,
                packet.payload.hex(" "),
            )
            state = replace(state, unknown_packets=state.unknown_packets + 1)
        self.async_set_updated_data(state)

    @callback
    def _handle_command_response(self, response: CommandResponse) -> None:
        """Latch the lockout flag if the panel ever reports a password failure.

        Nothing this integration sends carries a password — the whole command set runs on path A,
        which has none — so in normal operation this never fires. It exists because the cost of
        being wrong about that is high and asymmetric: **five** wrong passwords block remote
        operation at the panel until somebody walks to the keypad, and the flag has to be set on the
        **first**. AGENTS.md §6.

        The flag is never cleared automatically. Clearing it means the user has understood what
        happened, which is what the repair issue asks them to do.
        """
        if not response.locks_panel_out or self.auth_blocked:
            return
        self.auth_blocked = True
        LOGGER.warning(
            "Panel %s rejected a command with %s. No further password-carrying command will be "
            "sent from here: five of these block remote operation at the panel until someone "
            "performs a valid keypad operation",
            self.serial,
            response.ack.name,
        )
        async_report_lockout(self.hass, self.serial)

    @callback
    def _handle_event(
        self, event: PanelEvent, state: JflPanelState, now: datetime
    ) -> None:
        """Send a Contact ID event to the `event` entities and record that one arrived.

        The event itself travels on the dispatcher, not in the snapshot — see the module docstring.
        What goes in the snapshot is only the fact that an event was received and when, which is
        state and survives a restart harmlessly.
        """
        LOGGER.debug(
            "%s: dispatching event %s, partition %s",
            self.serial,
            event.code,
            event.partition,
        )
        self.async_set_updated_data(
            replace(
                state,
                last_event_at=now,
                last_event_code=event.code,
                zone_alerts=self._apply_zone_alert(event, state.zone_alerts),
            )
        )
        async_dispatcher_send(
            self.hass,
            signal_panel_event(self.config_entry.entry_id, self.serial),
            event,
        )

    @callback
    def _apply_zone_alert(
        self, event: PanelEvent, current: Mapping[int, frozenset[ZoneAlert]]
    ) -> Mapping[int, frozenset[ZoneAlert]]:
        """Fold a low-battery, supervision or tamper event into the per-zone latches.

        Returns *current* unchanged for every other code, which is almost all of them — and
        returning the same object matters: the coordinator is `always_update=False`, so an identical
        snapshot spares every entity a state write.
        """
        alert = zone_alert(event.code)
        if alert is None or event.is_fence:
            return current
        try:
            zone = int(event.subject)
        except ValueError:
            # These six codes all carry a zone number, so a non-numeric subject means a frame we
            # decoded wrongly rather than a condition. Dropping it beats latching it on zone 0.
            LOGGER.debug(
                "%s: event %s has a non-numeric zone %r",
                self.serial,
                event.code,
                event.subject,
            )
            return current

        condition, setting = alert
        held = current.get(zone, frozenset())
        updated = held | {condition} if setting else held - {condition}
        if updated == held:
            return current

        LOGGER.debug(
            "%s: zone %d %s %s (event %s)",
            self.serial,
            zone,
            "reports" if setting else "clears",
            condition,
            event.code,
        )
        alerts = dict(current)
        if updated:
            alerts[zone] = updated
        else:
            alerts.pop(zone, None)
        return alerts

    @callback
    def _handle_available(self, available: bool) -> None:
        """React to the connection watchdog.

        Logged **once** per transition, never per retry: a panel that redials every ninety seconds
        would otherwise fill the log with a pair of lines a minute. AGENTS.md §4.

        Both directions are `info`, matching the quality-scale `log-when-unavailable` rule exactly:
        it asks for `info` on both the disappearance and the return, on the grounds that this is
        about being able to find out *when* and *why*, not about severity. A panel that goes quiet
        is not the integration failing — the repair issue and the connectivity sensor are where
        anything more urgent than "here is what happened" belongs.
        """
        if available and self._warned_unavailable:
            LOGGER.info("Panel %s is reporting again", self.serial)
            self._warned_unavailable = False
        elif not available and not self._warned_unavailable:
            LOGGER.info(
                "Panel %s stopped reporting. Check that it is powered, on the network, and still "
                "programmed to report to this integration",
                self.serial,
            )
            self._warned_unavailable = True
        self.async_set_updated_data(replace(self.data, available=available))
