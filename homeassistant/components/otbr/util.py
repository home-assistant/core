"""Utility functions for the Open Thread Border Router integration."""

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import dataclasses
from functools import wraps
import logging
import math
import random
from typing import TYPE_CHECKING, Any, Concatenate, NamedTuple, cast

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionException
import python_otbr_api
from python_otbr_api import (
    PENDING_DATASET_DELAY_TIMER,
    PENDING_DATASET_TIMEOUT,
    tlv_parser,
)
from python_otbr_api.pskc import compute_pskc
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    MultiprotocolAddonManager,
    get_multiprotocol_addon_manager,
    is_multiprotocol_url,
)
from homeassistant.components.thread import (
    DatasetAddResult,
    async_add_dataset,
    async_get_store,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import API_TIMEOUT, DOMAIN

if TYPE_CHECKING:
    from . import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)


DATASET_LOCK_KEY: HassKey[asyncio.Lock] = HassKey("otbr_dataset_lock")
ISSUED_TIMESTAMPS_KEY: HassKey[IssuedTimestamps] = HassKey("otbr_issued_timestamps")
ISSUED_TIMESTAMPS_STORAGE_KEY = f"{DOMAIN}.issued_timestamps"
ISSUED_TIMESTAMPS_STORAGE_VERSION = 1

# From this REST API version the router registers pending datasets with the
# leader instead of writing them locally (ot-br-posix#3582).
_LEADER_REGISTERING_API = AwesomeVersion("0.6.0")

# Two reads within the API timeout, then the write waiting for the leader.
_WRITE_WINDOW_S = 2 * API_TIMEOUT + PENDING_DATASET_TIMEOUT


class _Migration(NamedTuple):
    """A migration under way from a network, as recorded on disk.

    The router it was handed to and the dataset sent are kept until it is
    recorded; the target and the arrival deadline until the mesh arrives.
    """

    target: str
    router: str | None
    arrives: float
    dataset: str


class _Record(NamedTuple):
    """What is recorded for a network, as handed back to async_restore."""

    stamp: tuple[int, int]
    until: float
    migration: _Migration | None


def _seconds_left(until: float) -> int:
    """Return the whole seconds until a deadline, zero once it has passed."""
    return max(0, math.ceil(until - dt_util.utcnow().timestamp()))


def parse_dataset(
    tlvs: bytes,
) -> dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]:
    """Parse a dataset the router returned, as an error of its own if it cannot be."""
    try:
        return tlv_parser.parse_tlv(tlvs.hex())
    except tlv_parser.TLVError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="router_dataset_invalid"
        ) from err


def _channel_of(
    dataset: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
) -> int | None:
    """Return the channel a dataset names, if any."""
    item = dataset.get(MeshcopTLVType.CHANNEL)
    return item.channel if isinstance(item, tlv_parser.Channel) else None


def _on_channel(
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], channel: int
) -> tuple[dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], tuple[int, int]]:
    """Return an active dataset moved to a channel, and its stamp.

    Stamped as the library stamps a channel change: one second above the
    active timestamp, its ticks kept, or from one when there is none.
    """
    moved = dict(active)
    moved[MeshcopTLVType.CHANNEL] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.CHANNEL, bytes([0, channel >> 8, channel & 0xFF])
    )
    stamp = active.get(MeshcopTLVType.ACTIVETIMESTAMP)
    seconds, ticks, authoritative = (
        (stamp.seconds + 1, stamp.ticks, stamp.authoritative)
        if isinstance(stamp, tlv_parser.Timestamp)
        else (1, 0, False)
    )
    moved[MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP,
        seconds=seconds,
        ticks=ticks,
        authoritative=authoritative,
    )
    return moved, (seconds, ticks)


class IssuedTimestamps:
    """The newest timestamp this integration has issued, per source network.

    Keyed by extended PAN ID: a busy network must not raise the floor for the
    others, which would eventually exhaust their timestamps too.

    Kept on disk, not only in memory: a pending dataset takes its delay to
    reach every router on the mesh, and a restart inside that window must not
    let the next migration hand out the stamp again.

    The record also remembers until when the issued dataset is propagating.
    A newer stamp alone does not protect the mesh in that window: a second
    migration handed to a router that has not learned the first dataset yet
    supersedes it, and devices that only ever received the first one switch
    to a different network than the rest.

    It also remembers each migration under way: the network it moves to and
    until when its mesh arrives there, since that network counts as
    mid-change until then; the router it was handed to, until the migration
    is recorded, since a write the router never answered may have landed,
    and that router later found on the target settles it; and the dataset
    sent, so that nothing else goes out under the target's name with other
    settings while that is unsettled. A change of a network's own settings
    is kept the same way until the store follows it, the network being its
    own target.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the record."""
        self._store = Store[dict[str, dict[str, Any]]](
            hass,
            ISSUED_TIMESTAMPS_STORAGE_VERSION,
            ISSUED_TIMESTAMPS_STORAGE_KEY,
            # This file exists to survive an ill-timed restart; the same
            # restart must not be able to truncate an in-place rewrite.
            atomic_writes=True,
        )
        self._issued: dict[str, tuple[int, int]] = {}
        self._until: dict[str, float] = {}
        self._migration: dict[str, _Migration] = {}

    async def async_load(self) -> None:
        """Load what was issued before the last restart."""
        if data := await self._store.async_load():
            for xpan, record in data.items():
                seconds, ticks = record["timestamp"]
                self._issued[xpan] = (seconds, ticks)
                self._until[xpan] = record["until"]
                if target := record.get("target"):
                    self._migration[xpan] = _Migration(
                        target,
                        record.get("router"),
                        record.get("arrives", record["until"]),
                        record.get("dataset", ""),
                    )

    def get(self, extended_pan_id: str) -> tuple[int, int]:
        """Return the newest timestamp issued for a network."""
        return self._issued.get(extended_pan_id, (0, 0))

    def seconds_propagating(self, extended_pan_id: str) -> int:
        """Return how long the dataset issued for a network keeps propagating.

        Zero once its delay has expired, or when nothing was issued.
        """
        return _seconds_left(self._until.get(extended_pan_id, 0))

    def seconds_in_flight(self, extended_pan_id: str) -> int:
        """Return how long a network stays mid-change.

        While a dataset issued for it propagates, or a mesh sent onto it from
        another network counts down to arrive: moving its mesh before then
        leaves part of it behind.
        """
        arriving = (
            _seconds_left(migration.arrives)
            for migration in self._migration.values()
            if migration.target == extended_pan_id
        )
        return max(self.seconds_propagating(extended_pan_id), *arriving, 0)

    def attempted(self, extended_pan_id: str) -> list[str]:
        """Return the datasets sent onto a network and not recorded yet.

        By a migration or by a change of its own settings, whatever their
        age: a write whose answer was lost may have landed, so the network
        may be running it, and only the router it was handed to, found
        there, can tell.
        """
        return [
            migration.dataset
            for migration in self._migration.values()
            if migration.target == extended_pan_id and migration.router is not None
        ]

    def sent(self, extended_pan_id: str) -> str | None:
        """Return the dataset a network's unsettled migration or change sent."""
        migration = self._migration.get(extended_pan_id)
        if migration is None or migration.router is None:
            return None
        return migration.dataset

    def record(self, extended_pan_id: str) -> _Record | None:
        """Return what is recorded for a network, to hand to async_restore."""
        if extended_pan_id not in self._issued:
            return None
        return _Record(
            self._issued[extended_pan_id],
            self._until[extended_pan_id],
            self._migration.get(extended_pan_id),
        )

    def migration_source(
        self, target_extended_pan_id: str, router_entry_id: str
    ) -> str | None:
        """Return the network an unrecorded migration left for this one.

        Known from the moment a migration's dataset is handed to a router
        until the migration is recorded; in between, that router found on the
        target says the write landed although its answer was lost. Another
        router on the target says nothing: it may have been there all along.
        A change of a network's own settings names the network as its source.
        """
        return next(
            (
                source
                for source, migration in self._migration.items()
                if migration.target == target_extended_pan_id
                and migration.router == router_entry_id
            ),
            None,
        )

    async def async_confirm(self, extended_pan_id: str) -> None:
        """Forget the router and the dataset of a migration now recorded.

        Its target and deadline stay: the mesh is still on its way there. The
        dataset is in the store now, and its credentials need no second copy.
        """
        migration = self._migration.get(extended_pan_id)
        if migration is not None and migration.router is not None:
            self._migration[extended_pan_id] = _Migration(
                migration.target, None, migration.arrives, ""
            )
            await self._async_save()

    async def async_sent(
        self, extended_pan_id: str, router_entry_id: str, dataset: str
    ) -> None:
        """Keep a dataset sent to change a network's own settings, until settled.

        Kept like an unanswered migration, for the router it was handed to,
        found running the dataset, to settle: the write may go unanswered, and
        a read after it may fail. A migration still to be settled is left in
        place, though, since its router may yet be found on its target.
        """
        migration = self._migration.get(extended_pan_id)
        if (
            migration is not None
            and migration.router is not None
            and migration.target != extended_pan_id
        ):
            return
        self._migration[extended_pan_id] = _Migration(
            extended_pan_id,
            router_entry_id,
            self._until.get(extended_pan_id, 0),
            dataset,
        )
        await self._async_save()

    async def async_settle(self, extended_pan_id: str) -> None:
        """Forget the dataset sent to change a network's own settings.

        Once the store holds what the mesh runs. A migration still to be
        settled is not that and stays.
        """
        migration = self._migration.get(extended_pan_id)
        if migration is not None and migration.target == extended_pan_id:
            await self.async_confirm(extended_pan_id)

    async def async_set(
        self, extended_pan_id: str, timestamp: tuple[int, int], *, until: float
    ) -> None:
        """Record a timestamp about to be issued for a network.

        Written through before the caller hands the dataset to the router:
        delaying the save would reopen the window this record exists to close.

        The stamp never goes down, only the window moves: a channel change
        through a router that missed an earlier migration is stamped from
        that router's stale active dataset, and must not lower the floor the
        next migration steps above.
        """
        self._issued[extended_pan_id] = max(self.get(extended_pan_id), timestamp)
        self._until[extended_pan_id] = until
        await self._async_save()

    async def async_restore(self, extended_pan_id: str, record: _Record | None) -> None:
        """Put back what record() returned, when the issued dataset never left.

        A router that refused the write leaves no migration under way; the
        window recorded for it would only refuse every retry until it expired.
        An earlier migration still to be settled is put back with the rest,
        since the refused write may have been a retry over it.
        """
        if record is None:
            self._issued.pop(extended_pan_id, None)
            self._until.pop(extended_pan_id, None)
            self._migration.pop(extended_pan_id, None)
        else:
            self._issued[extended_pan_id] = record.stamp
            self._until[extended_pan_id] = record.until
            if record.migration is None:
                self._migration.pop(extended_pan_id, None)
            else:
                self._migration[extended_pan_id] = record.migration
        await self._async_save()

    async def async_write(
        self,
        data: OTBRData,
        extended_pan_id: str,
        timestamp: tuple[int, int],
        delay: float,
        write: Callable[[], Coroutine[Any, Any, None]],
        migration: tuple[str, str, str] | None = None,
    ) -> None:
        """Run a pending dataset write inside the window it opens on the mesh.

        `migration` names the network a migration moves to, the router it is
        handed to and the dataset sent. The router is kept until the migration
        is recorded, so one whose answer was lost can be finished once that
        router is found there; the target, with the window's deadline, until
        the mesh arrives.

        The record is written before the write and deliberately outlasts the
        delay: the router starts its own timer only once it accepts the
        dataset, up to _WRITE_WINDOW_S later, and a crash in between leaves
        this record as the only one. Erring long costs a late retry after
        such a crash; erring short lets the next migration overtake a mesh
        still counting down. The record is tightened to the real deadline
        once the write completes.
        """
        previous = self.record(extended_pan_id)

        async def set_until(until: float) -> None:
            if migration is not None:
                target, router, dataset = migration
                self._migration[extended_pan_id] = _Migration(
                    target, router, until, dataset
                )
            await self.async_set(extended_pan_id, timestamp, until=until)

        await set_until(dt_util.utcnow().timestamp() + delay + _WRITE_WINDOW_S)
        started = dt_util.utcnow().timestamp()
        try:
            await write()
        except HomeAssistantError as err:
            cause = err.__cause__
            if isinstance(cause, python_otbr_api.PendingDatasetOutcomeUnknownError):
                # No answer from the leader: the dataset may well be propagating.
                in_flight: bool | None = True
            elif isinstance(
                cause,
                (
                    python_otbr_api.OTBRError,
                    aiohttp.ClientConnectorError,
                    TimeoutError,
                ),
            ):
                # Refused, never connected, or timed out before the write (a
                # timeout of the write itself is an unknown outcome above):
                # nothing was written.
                in_flight = None
            else:
                # The connection dropped: ask the router. One writing locally
                # holds the dataset for the whole delay, so none within it
                # means the write never arrived.
                in_flight = await _router_holds_a_pending_dataset(data)
                if not in_flight and dt_util.utcnow().timestamp() < started + delay:
                    in_flight = None
            if in_flight is None:
                await self.async_restore(extended_pan_id, previous)
            elif in_flight:
                # Measured from the latest moment the write can have landed.
                await set_until(dt_util.utcnow().timestamp() + delay)
            else:
                # Applied already or never written: the window is handed
                # back, the stamp kept in case the mesh is running it.
                await set_until(previous.until if previous else 0)
            raise
        # From when the router accepted the write, not when the request
        # left, or a slow request would end the window early.
        await set_until(dt_util.utcnow().timestamp() + delay)

    async def _async_save(self) -> None:
        data: dict[str, dict[str, Any]] = {}
        for xpan, stamp in self._issued.items():
            record: dict[str, Any] = {
                "timestamp": list(stamp),
                "until": self._until[xpan],
            }
            if migration := self._migration.get(xpan):
                record["target"] = migration.target
                record["arrives"] = migration.arrives
                if migration.router is not None:
                    record["router"] = migration.router
                    record["dataset"] = migration.dataset
            data[xpan] = record
        await self._store.async_save(data)


@singleton(ISSUED_TIMESTAMPS_KEY, async_=True)
async def async_get_issued_timestamps(hass: HomeAssistant) -> IssuedTimestamps:
    """Return the record of issued timestamps, loading it on first use."""
    issued = IssuedTimestamps(hass)
    await issued.async_load()
    return issued


async def _router_holds_a_pending_dataset(data: OTBRData) -> bool:
    """Return whether the router has a pending dataset, assuming it does.

    Asked after a write whose outcome the connection did not report. Any
    pending dataset means one is propagating, whether or not it is the one
    that was being written. A router that cannot be asked leaves the
    question open, and the answer that protects the mesh is that there is
    one.

    So does a router that registers the dataset with the Thread leader:
    its own copy only arrives once the leader hands the dataset back to
    the mesh, so not holding one right after the write says nothing about
    whether the write landed. It is not asked.
    """
    try:
        version = await data.get_api_version()
        if version is not None and AwesomeVersion(version) >= _LEADER_REGISTERING_API:
            return True
        return await data.get_pending_dataset_tlvs() is not None
    except HomeAssistantError, AwesomeVersionException:
        return True


@callback
def async_get_dataset_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the lock serializing dataset mutations.

    It covers every config entry, and is acquired by callers rather than by
    the OTBRData methods, so a sequence that reads the router's state and
    writes it back stays atomic: concurrent writers would otherwise work from
    state the other has already replaced, and the mesh silently ignores
    whichever pending dataset is not the newest while its writer still
    reports success.
    """
    if (lock := hass.data.get(DATASET_LOCK_KEY)) is None:
        lock = hass.data[DATASET_LOCK_KEY] = asyncio.Lock()
    return lock


INSECURE_NETWORK_KEYS = (
    # Thread web UI default
    bytes.fromhex("00112233445566778899AABBCCDDEEFF"),
)

INSECURE_PASSPHRASES = (
    # Thread web UI default
    "j01Nme",
    # Thread documentation default
    "J01NME",
)


class GetBorderAgentIdNotSupported(HomeAssistantError):
    """Raised from python_otbr_api.GetBorderAgentIdNotSupportedError."""


def compose_default_network_name(pan_id: int) -> str:
    """Generate a default network name."""
    return f"ha-thread-{pan_id:04x}"


def generate_random_pan_id() -> int:
    """Generate a random PAN ID."""
    # PAN ID is 2 bytes, 0xffff is reserved for broadcast
    return random.randint(0, 0xFFFE)


def _handle_otbr_error[**_P, _R](
    func: Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]]:
    """Handle OTBR errors.

    The verdicts on a pending dataset write each get their own error: the
    caller has to tell "nothing happened" from "something may have", and
    the user is told the router's reason.
    """

    @wraps(func)
    async def _func(self: OTBRData, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except python_otbr_api.PendingDatasetConflictError as exc:
            # A write the library refused because the mesh is already
            # mid-change. Every caller of one gets the same answer -- wait
            # the in-flight change out, do not retry -- so it is told here
            # rather than reported as a generic API failure.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pending_dataset_in_place",
            ) from exc
        except python_otbr_api.PendingDatasetRejectedError as exc:
            # The router is not attached, the leader refused the dataset, or
            # an earlier registration is still being answered.
            if exc.reason:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="pending_dataset_refused_reason",
                    translation_placeholders={"reason": exc.reason},
                ) from exc
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pending_dataset_refused"
            ) from exc
        except python_otbr_api.PendingDatasetOutcomeUnknownError as exc:
            # The leader did not answer in time, so the write may have landed.
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pending_dataset_unanswered"
            ) from exc
        except (python_otbr_api.OTBRError, aiohttp.ClientError, TimeoutError) as exc:
            raise HomeAssistantError("Failed to call OTBR API") from exc

    return _func


@dataclasses.dataclass
class OTBRData:
    """Container for OTBR data."""

    url: str
    api: python_otbr_api.OTBR
    entry_id: str

    @_handle_otbr_error
    async def factory_reset(self, hass: HomeAssistant) -> None:
        """Reset the router."""
        try:
            await self.api.factory_reset()
        except python_otbr_api.FactoryResetNotSupportedError:
            _LOGGER.warning(
                "OTBR does not support factory reset, attempting to delete dataset"
            )
            await self.delete_active_dataset()
        await update_unique_id(
            hass,
            hass.config_entries.async_get_entry(self.entry_id),
            await self.get_border_agent_id(),
        )

    @_handle_otbr_error
    async def get_border_agent_id(self) -> bytes:
        """Get the border agent ID or None if not supported by the router."""
        try:
            return await self.api.get_border_agent_id()
        except python_otbr_api.GetBorderAgentIdNotSupportedError as exc:
            raise GetBorderAgentIdNotSupported from exc

    @_handle_otbr_error
    async def get_api_version(self) -> str | None:
        """Get the REST API version, or None for a router that has none."""
        return await self.api.get_api_version()

    @_handle_otbr_error
    async def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the router."""
        return await self.api.set_enabled(enabled)

    @_handle_otbr_error
    async def get_active_dataset(self) -> python_otbr_api.ActiveDataSet | None:
        """Get current active operational dataset, or None."""
        return await self.api.get_active_dataset()

    @_handle_otbr_error
    async def get_active_dataset_tlvs(self) -> bytes | None:
        """Get current active operational dataset in TLVS format, or None."""
        return await self.api.get_active_dataset_tlvs()

    @_handle_otbr_error
    async def get_pending_dataset_tlvs(self) -> bytes | None:
        """Get current pending operational dataset in TLVS format, or None."""
        return await self.api.get_pending_dataset_tlvs()

    @_handle_otbr_error
    async def create_active_dataset(
        self, dataset: python_otbr_api.ActiveDataSet
    ) -> None:
        """Create an active operational dataset."""
        return await self.api.create_active_dataset(dataset)

    @_handle_otbr_error
    async def delete_active_dataset(self) -> None:
        """Delete the active operational dataset."""
        return await self.api.delete_active_dataset()

    @_handle_otbr_error
    async def set_active_dataset_tlvs(self, dataset: bytes) -> None:
        """Set current active operational dataset in TLVS format."""
        await self.api.set_active_dataset_tlvs(dataset)

    @_handle_otbr_error
    async def set_pending_dataset_tlvs(self, dataset: bytes) -> None:
        """Set the pending operational dataset in TLVS format.

        Refused while a pending dataset is in place; a border router that
        registers the dataset with the Thread leader (ot-br-posix#3582) can
        also reject it, or report no verdict. The wrapper names each.
        """
        await self.api.set_pending_dataset_tlvs(dataset)

    async def set_channel(
        self,
        hass: HomeAssistant,
        channel: int,
        delay: float = PENDING_DATASET_DELAY_TIMER / 1000,
    ) -> None:
        """Change the channel with a pending dataset, recording it as propagating.

        The change reaches every router on the mesh, so it is recorded like a
        migration: a migration of the mesh is refused until the delay expires,
        and stamped above the change afterwards. Refused while a migration is
        propagating or arriving, for the same reason. The caller holds the
        dataset lock.

        The dataset the mesh moves to is stored, or the store would keep the
        old channel and a migration to the stored network would move the mesh
        back. It is kept on the network's record first, as a dataset sent: a
        write the router never answered may have landed, a read after the
        write can fail, and the router found running it settles it then.
        """
        if not 11 <= channel <= 26:
            # Refused before a dataset is built on it; the library refuses the
            # write itself, but only once asked.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_channel",
                translation_placeholders={"channel": str(channel)},
            )
        active_tlvs = await self.get_active_dataset_tlvs()
        if active_tlvs is None:
            # The library refuses the write itself.
            await self._set_channel(channel, delay)
            return
        active = parse_dataset(active_tlvs)
        if (xpan := active.get(MeshcopTLVType.EXTPANID)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="router_dataset_invalid"
            )
        extended_pan_id = str(xpan).lower()
        issued = await async_get_issued_timestamps(hass)
        if remaining := issued.seconds_in_flight(extended_pan_id):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="migration_in_flight",
                translation_placeholders={"remaining": str(remaining)},
            )
        moved, stamp = _on_channel(active, channel)
        try:
            await issued.async_write(
                self,
                extended_pan_id,
                stamp,
                delay,
                lambda: self._set_channel(channel, delay),
            )
        except HomeAssistantError as err:
            if isinstance(
                err.__cause__, python_otbr_api.PendingDatasetOutcomeUnknownError
            ):
                # The unknown outcome is the error to report, not a read.
                with suppress(HomeAssistantError):
                    await self._async_store_channel_change(
                        hass, issued, extended_pan_id, channel, moved, False
                    )
            raise
        await self._async_store_channel_change(
            hass, issued, extended_pan_id, channel, moved, True
        )

    @_handle_otbr_error
    async def _set_channel(self, channel: int, delay: float) -> None:
        await self.api.set_channel(channel, delay=int(delay * 1000))

    async def _async_store_channel_change(
        self,
        hass: HomeAssistant,
        issued: IssuedTimestamps,
        extended_pan_id: str,
        channel: int,
        moved: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
        landed: bool,
    ) -> None:
        """Store the dataset the mesh moves to, flushed to disk at once.

        Kept on the network's record before the router is read: a read can
        fail, and the router found running the dataset settles it then. What
        the router holds is stored -- its pending copy, or its active dataset
        once that shows the channel -- else, for a write the router answered,
        the dataset as sent, since a router that registers with the leader
        holds its own copy only once the leader hands it back. Flushed because
        a crash inside the store's save delay would leave the old channel on
        disk. Raises when the store kept a dataset at least as new, like a
        migration does: the mesh moves to this one regardless.
        """
        await issued.async_sent(
            extended_pan_id, self.entry_id, tlv_parser.encode_tlv(moved)
        )
        try:
            held = await self._async_dataset_held(channel)
        except HomeAssistantError:
            if not landed:
                raise
            # The router answered: the write landed, readable or not.
            held = None
        if held is None:
            if not landed:
                return
            held = moved
        result = await async_add_dataset(hass, DOMAIN, tlv_parser.encode_tlv(held))
        await (await async_get_store(hass)).async_save()
        await issued.async_settle(extended_pan_id)
        if result is DatasetAddResult.DISCARDED:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="dataset_discarded"
            )

    async def _async_dataset_held(
        self, channel: int
    ) -> dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem] | None:
        """Return the router's copy of a channel change, once it holds one.

        Its pending copy, or its active dataset once that shows the channel.
        """
        if (tlvs := await self.get_pending_dataset_tlvs()) is None:
            if (tlvs := await self.get_active_dataset_tlvs()) is None:
                return None
            dataset = parse_dataset(tlvs)
            if _channel_of(dataset) != channel:
                return None
        else:
            dataset = parse_dataset(tlvs)
        dataset.pop(MeshcopTLVType.DELAYTIMER, None)
        dataset.pop(MeshcopTLVType.PENDINGTIMESTAMP, None)
        return dataset

    @_handle_otbr_error
    async def get_extended_address(self) -> bytes:
        """Get extended address (EUI-64)."""
        return await self.api.get_extended_address()

    @_handle_otbr_error
    async def get_coprocessor_version(self) -> str:
        """Get coprocessor firmware version."""
        return await self.api.get_coprocessor_version()


async def get_allowed_channel(hass: HomeAssistant, otbr_url: str) -> int | None:
    """Return the allowed channel, or None if there's no restriction."""
    if not is_multiprotocol_url(otbr_url):
        # The OTBR is not sharing the radio, no restriction
        return None

    multipan_manager: MultiprotocolAddonManager = await get_multiprotocol_addon_manager(
        hass
    )
    return multipan_manager.async_get_channel()


async def _warn_on_channel_collision(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
) -> None:
    """Warn user if OTBR and ZHA attempt to use different channels."""

    def delete_issue() -> None:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"otbr_zha_channel_collision_{otbrdata.entry_id}",
        )

    if (allowed_channel := await get_allowed_channel(hass, otbrdata.url)) is None:
        delete_issue()
        return

    dataset = tlv_parser.parse_tlv(dataset_tlvs.hex())

    if (channel_s := dataset.get(MeshcopTLVType.CHANNEL)) is None:
        delete_issue()
        return
    channel = cast(tlv_parser.Channel, channel_s).channel

    if channel == allowed_channel:
        delete_issue()
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"otbr_zha_channel_collision_{otbrdata.entry_id}",
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="otbr_zha_channel_collision",
        translation_placeholders={
            "otbr_channel": str(channel),
            "zha_channel": str(allowed_channel),
        },
    )


def _warn_on_default_network_settings(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
) -> None:
    """Warn user if insecure default network settings are used."""
    dataset = tlv_parser.parse_tlv(dataset_tlvs.hex())
    insecure = False

    if (
        network_key := dataset.get(MeshcopTLVType.NETWORKKEY)
    ) is not None and network_key.data in INSECURE_NETWORK_KEYS:
        insecure = True
    if (
        not insecure
        and MeshcopTLVType.EXTPANID in dataset
        and MeshcopTLVType.NETWORKNAME in dataset
        and MeshcopTLVType.PSKC in dataset
    ):
        ext_pan_id = dataset[MeshcopTLVType.EXTPANID]
        network_name = cast(tlv_parser.NetworkName, dataset[MeshcopTLVType.NETWORKNAME])
        pskc = dataset[MeshcopTLVType.PSKC].data
        for passphrase in INSECURE_PASSPHRASES:
            if pskc == compute_pskc(ext_pan_id.data, network_name.name, passphrase):
                insecure = True
                break

    if insecure:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"insecure_thread_network_{otbrdata.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="insecure_thread_network",
        )
    else:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"insecure_thread_network_{otbrdata.entry_id}",
        )


async def update_issues(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
) -> None:
    """Raise or clear repair issues related to network settings."""
    await _warn_on_channel_collision(hass, otbrdata, dataset_tlvs)
    _warn_on_default_network_settings(hass, otbrdata, dataset_tlvs)


async def update_unique_id(
    hass: HomeAssistant, entry: OTBRConfigEntry | None, border_agent_id: bytes
) -> None:
    """Update the config entry's unique_id if not matching."""
    border_agent_id_hex = border_agent_id.hex()
    if entry and entry.source == SOURCE_USER and entry.unique_id != border_agent_id_hex:
        _LOGGER.debug(
            "Updating unique_id of entry %s from %s to %s",
            entry.entry_id,
            entry.unique_id,
            border_agent_id_hex,
        )
        hass.config_entries.async_update_entry(entry, unique_id=border_agent_id_hex)
