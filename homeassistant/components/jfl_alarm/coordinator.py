"""One coordinator per panel, fed by pushes from the listener.

`DataUpdateCoordinator` is used with `update_interval=None`: nothing polls on Home Assistant's
schedule. The listener pushes and `async_set_updated_data` fans the new snapshot out. The panel is
polled for status, but that poll belongs to the connection rather than to the update loop.

Four decisions here are deliberate and easy to undo by accident:

* `data` is never `None`, and `async_config_entry_first_refresh` is never called. A panel typically
  dials in ten to sixty seconds after a restart, so a first refresh would fail the entry setup for a
  panel that is merely still booting.
* Availability comes from the connection, not from `last_update_success`.
* Contact ID events go out on a dispatcher signal rather than in the snapshot. A snapshot is
  replayed to every entity on every update and again after a restart, so an event kept in one would
  re-fire. Only the timestamp of the last event is state.
* Nothing is optimistic. A command never writes a state; it schedules two status re-reads, and the
  panel's own answer is what the entities show. Arming can return a status frame that still shows a
  zone open, which the panel then auto-bypasses a second later.
"""

import asyncio
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from pyjfl import (
    UNKNOWN_MODEL,
    ArmMode,
    CommandResponse,
    ConnectionInfo,
    GlobalZoneOptions,
    HolidayRecord,
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
    WirelessRecord,
    ZoneRecord,
    build_arm,
    build_arm_away,
    build_arm_stay,
    build_disarm,
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
)

# `MAX_WIRELESS` and `REGIONS` are not re-exported from `pyjfl`'s top-level namespace yet.
from pyjfl.protocol.programming import REGIONS

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_PROGRAMMING_READ_INTERVAL,
    DEFAULT_STATUS_INTERVAL,
    DOMAIN,
    LOGGER,
    PROGRAMMING_READ_FIRST_DELAY,
    PROGRAMMING_READ_GAP,
    PROGRAMMING_READ_IDLE_SLEEP,
    PROGRAMMING_READ_RETRIES,
    VERIFY_DELAYS,
    signal_panel_event,
)
from .device import async_apply_programmed_names, async_refresh_panel_device

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from homeassistant.config_entries import ConfigSubentry

    from . import JflConfigEntry


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

    def partition(self, number: int) -> PartitionState | None:
        """Return partition *number* (1-based), or `None` if this panel has no such partition."""
        partitions = self.partitions
        if 1 <= number <= len(partitions):
            return partitions[number - 1]
        return None


@dataclass(frozen=True, slots=True)
class JflProgramming:
    """What the panel's programming says about itself, once it has been read.

    Separate from `JflPanelState` on purpose. The status snapshot is replaced many times a minute;
    this changes only when somebody reprograms the panel, and the panel tells us when that happened
    through `KP`. Keeping them apart means a full read is not thrown away by the next status frame.

    No user access codes are here, and none can be: `UserRecord` carries `has_code` and the parser
    never returns the code itself.
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

    incomplete: tuple[str, ...] = ()
    """Regions that did not come back. Named rather than counted, so "the zone names are missing"
    is answerable without re-reading anything."""

    @property
    def read(self) -> bool:
        """Whether a programming read has ever completed on this panel."""
        return self.read_at is not None

    def zone_name(self, number: int) -> str:
        """Return a zone's programmed name, or an empty string if it has none or is unknown.

        Empty rather than a placeholder: a zone with no name reads as its bare number, never as
        `Zone 3 (unnamed)`.
        """
        record = self.zones.get(number)
        return record.name if record is not None else ""

    def partition_name(self, number: int) -> str:
        """Return a partition's programmed name, or an empty string."""
        record = self.partitions.get(number)
        return record.name if record is not None else ""


@dataclass(slots=True)
class _Discovery:
    """What the platforms have already created, so a re-run adds only what is new."""

    partitions: set[int] = field(default_factory=set)


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

        This is what makes the automatic read safe: a panel that does not implement the
        programming commands is asked once and then left alone, rather than hammered with thirty
        requests on every reconnection."""

        self.auth_blocked = False
        """Set by a `0xA1` or `0xAA` reply, and never cleared on its own. See `_handle_packet`."""

        self._unsubscribe: list[Callable[[], None]] = []
        self._poll_task: asyncio.Task[None] | None = None
        self._programming_task: asyncio.Task[None] | None = None
        self._warned_unavailable = False
        # `data` must never be None: entities are added before any panel has dialled in.
        self.async_set_updated_data(JflPanelState())

    # --- capabilities ---------------------------------------------------------------------------

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

        Once is also the probe: if the first read comes back with nothing, the panel does not
        answer `0x44` and is never asked again automatically.

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
        return status.programming_checksum != self.programming.checksum

    async def async_refresh_status(self) -> None:
        """Ask for a status frame now. Raises if the panel is not connected."""
        LOGGER.debug("%s: status refresh requested", self.serial)
        await self.link.async_request_status()

    # --- reading the programming ------------------------------------------------------------------

    async def async_read_programming(self) -> JflProgramming:
        """Read the panel's programming into a structured snapshot.

        A read, not a command, so it runs in `read_only` mode — the same reasoning that keeps the
        status poll running.

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
                partitions={
                    number: record.name
                    for number, record in programming.partitions.items()
                },
            )
            # Entities read names from `self.programming`, which is not part of the snapshot, so
            # they have to be told to look again.
            self.async_update_listeners()
            return programming

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
        """Arm *partition* (1-based) in *mode*.

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
        """Refuse to send anything while the panel is in read-only mode."""
        if self.read_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="read_only",
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
        being wrong about that is high and asymmetric: five wrong passwords block remote operation
        at the panel until somebody walks to the keypad, so the flag is set on the first.

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
            )
        )
        async_dispatcher_send(
            self.hass,
            signal_panel_event(self.config_entry.entry_id, self.serial),
            event,
        )

    @callback
    def _handle_available(self, available: bool) -> None:
        """React to the connection watchdog.

        Logged once per transition, never per retry: a panel that redials every ninety seconds
        would otherwise fill the log with a pair of lines a minute.

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
