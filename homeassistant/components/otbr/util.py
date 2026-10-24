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
    from .types import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)


DATASET_LOCK_KEY: HassKey[asyncio.Lock] = HassKey("otbr_dataset_lock")
PROPAGATION_WINDOWS_KEY: HassKey[PropagationWindows] = HassKey(
    "otbr_propagation_windows"
)
PROPAGATION_WINDOWS_STORAGE_KEY = f"{DOMAIN}.propagation_windows"
PROPAGATION_WINDOWS_STORAGE_VERSION = 1

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
    """Parse dataset TLVs, raising router_dataset_invalid when malformed."""
    try:
        return tlv_parser.parse_tlv(tlvs.hex())
    except tlv_parser.TLVError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="router_dataset_invalid"
        ) from err


def timestamp_parts(
    entries: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    tag: MeshcopTLVType,
) -> tuple[int, int]:
    """Return the (seconds, ticks) of the timestamp under tag, (0, 0) when absent."""
    item = entries.get(tag)
    if isinstance(item, tlv_parser.Timestamp):
        return (item.seconds, item.ticks)
    return (0, 0)


def _on_channel(
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    channel: int,
    floor: tuple[int, int],
) -> tuple[dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], tuple[int, int]]:
    """Return the active dataset moved to a channel, and its new timestamp.

    Stamped as python-otbr-api stamps a channel change, one second up, from
    the newer of the active timestamp and `floor`, the newest issued for the
    network: a router that missed a change would otherwise reuse its stamp.
    """
    moved = dict(active)
    moved[MeshcopTLVType.CHANNEL] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.CHANNEL, bytes([0, channel >> 8, channel & 0xFF])
    )
    stamp = active.get(MeshcopTLVType.ACTIVETIMESTAMP)
    seconds, ticks, authoritative = (
        (stamp.seconds, stamp.ticks, stamp.authoritative)
        if isinstance(stamp, tlv_parser.Timestamp)
        else (0, 0, False)
    )
    seconds = max(seconds, floor[0]) + 1
    try:
        moved[MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
            MeshcopTLVType.ACTIVETIMESTAMP,
            seconds=seconds,
            ticks=ticks,
            authoritative=authoritative,
        )
    except tlv_parser.TLVError as err:
        # The seconds no longer fit the wire format.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="timestamp_exhausted"
        ) from err
    return moved, (seconds, ticks)


class PropagationWindows:
    """Per network: the window, the newest timestamp issued, the migration under way.

    Kept on disk and across routers. A router that has not learned a pending
    dataset yet would accept a second one superseding it; a restart inside the
    window must not hand the stamp out again; and a migration whose answer was
    lost is finished once its router is found on the target.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the record."""
        self._store = Store[dict[str, Any]](
            hass,
            PROPAGATION_WINDOWS_STORAGE_VERSION,
            PROPAGATION_WINDOWS_STORAGE_KEY,
            # A restart mid-write must not truncate the record.
            atomic_writes=True,
        )
        self._issued: dict[str, tuple[int, int]] = {}
        self._until: dict[str, float] = {}
        self._migration: dict[str, _Migration] = {}

    async def async_load(self) -> None:
        """Load the record; a bare deadline is a window recorded before the stamps."""
        if not (data := await self._store.async_load()):
            return
        for xpan, record in data.items():
            if not isinstance(record, dict):
                self._until[xpan] = record
                continue
            seconds, ticks = record["timestamp"]
            self._issued[xpan] = (seconds, ticks)
            self._until[xpan] = record["until"]
            if target := record.get("target"):
                self._migration[xpan] = _Migration(
                    target,
                    record.get("router"),
                    record["arrives"],
                    record.get("dataset", ""),
                )

    def get(self, extended_pan_id: str) -> tuple[int, int]:
        """Return the newest timestamp issued for a network."""
        return self._issued.get(extended_pan_id, (0, 0))

    def seconds_left(self, extended_pan_id: str) -> int:
        """Return the seconds a network's window has left, zero when none is open."""
        return _seconds_left(self._until.get(extended_pan_id, 0))

    def seconds_in_flight(self, extended_pan_id: str) -> int:
        """Return how long a network is mid-change: its window, or a mesh arriving."""
        arriving = (
            _seconds_left(migration.arrives)
            for migration in self._migration.values()
            if migration.target == extended_pan_id
        )
        return max(self.seconds_left(extended_pan_id), *arriving, 0)

    def seconds_until_landed(self, extended_pan_id: str, router_entry_id: str) -> int:
        """Return how long a write this router was handed has left to land."""
        migration = self._migration.get(extended_pan_id)
        if migration is None or migration.router != router_entry_id:
            return 0
        return _seconds_left(migration.arrives)

    def attempted(self, extended_pan_id: str) -> list[str]:
        """Return the datasets sent onto a network and not recorded yet."""
        return [
            migration.dataset
            for migration in self._migration.values()
            if migration.target == extended_pan_id and migration.router is not None
        ]

    def unsettled(self, extended_pan_id: str) -> _Migration | None:
        """Return a network's migration or change still to be settled, if any."""
        migration = self._migration.get(extended_pan_id)
        if migration is None or migration.router is None:
            return None
        return migration

    def sent(self, extended_pan_id: str) -> str | None:
        """Return the dataset a network's unsettled migration or change sent."""
        migration = self.unsettled(extended_pan_id)
        return None if migration is None else migration.dataset

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
        """Return the network an unrecorded migration left for this one."""
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
        """Forget the router and dataset of a recorded migration; its deadline stays."""
        migration = self._migration.get(extended_pan_id)
        if migration is not None and migration.router is not None:
            self._migration[extended_pan_id] = _Migration(
                migration.target, None, migration.arrives, ""
            )
            await self._async_save()

    async def async_forget(self, extended_pan_id: str) -> None:
        """Drop a network's migration: one whose write never left its router."""
        if self._migration.pop(extended_pan_id, None) is not None:
            await self._async_save()

    async def async_settle(self, extended_pan_id: str) -> None:
        """Forget the dataset sent to change a network's own settings."""
        migration = self._migration.get(extended_pan_id)
        if migration is not None and migration.target == extended_pan_id:
            await self.async_confirm(extended_pan_id)

    async def async_set(
        self, extended_pan_id: str, timestamp: tuple[int, int], *, until: float
    ) -> None:
        """Record a timestamp about to be issued; the stamp never goes down."""
        self._issued[extended_pan_id] = max(self.get(extended_pan_id), timestamp)
        self._until[extended_pan_id] = until
        await self._async_save()

    async def async_restore(self, extended_pan_id: str, record: _Record | None) -> None:
        """Put back what record() returned, when the issued dataset never left."""
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
        check: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Run a pending dataset write inside the window it opens on the mesh.

        `migration` names the network moved to, the router handed the dataset
        and the dataset sent. `check` runs last before the write, the window
        open; its refusal hands the window back. Opened before the write, wide
        enough to cover the write itself; then set to the delay from the
        router's answer, or handed back if nothing was written.
        """
        previous = self.record(extended_pan_id)
        # Another router's migration still to be settled is left in place.
        attempt = self.unsettled(extended_pan_id)
        if (
            migration is not None
            and attempt is not None
            and attempt.target != extended_pan_id
            and attempt.router != migration[1]
        ):
            migration = None

        async def set_until(until: float) -> None:
            if migration is not None:
                target, router, dataset = migration
                self._migration[extended_pan_id] = _Migration(
                    target, router, until, dataset
                )
            await self.async_set(extended_pan_id, timestamp, until=until)

        await set_until(dt_util.utcnow().timestamp() + delay + _WRITE_WINDOW_S)
        if check is not None:
            try:
                await check()
            except HomeAssistantError:
                await self.async_restore(extended_pan_id, previous)
                raise
        started = dt_util.utcnow().timestamp()
        try:
            await write()
        except HomeAssistantError as err:
            if not _write_may_have_landed(err):
                in_flight: bool | None = None
            elif isinstance(
                err.__cause__, python_otbr_api.PendingDatasetOutcomeUnknownError
            ):
                # The leader did not answer: it may be propagating.
                in_flight = True
            else:
                # The connection dropped: ask the router. One writing locally
                # holds the dataset for the whole delay.
                in_flight = await _router_holds_a_pending_dataset(data)
                if not in_flight and dt_util.utcnow().timestamp() < started + delay:
                    in_flight = None
            if in_flight is None:
                await self.async_restore(extended_pan_id, previous)
            elif in_flight:
                # Measured from the latest moment the write can have landed.
                await set_until(dt_util.utcnow().timestamp() + delay)
            else:
                # Applied already or never written; the stamp is kept.
                await set_until(previous.until if previous else 0)
            raise
        # Counted from the router's answer, not from the request.
        await set_until(dt_util.utcnow().timestamp() + delay)

    async def _async_save(self) -> None:
        data: dict[str, Any] = {}
        for xpan, until in self._until.items():
            record: dict[str, Any] = {
                "timestamp": list(self.get(xpan)),
                "until": until,
            }
            if migration := self._migration.get(xpan):
                record["target"] = migration.target
                record["arrives"] = migration.arrives
                if migration.router is not None:
                    record["router"] = migration.router
                    record["dataset"] = migration.dataset
            data[xpan] = record
        await self._store.async_save(data)


@singleton(PROPAGATION_WINDOWS_KEY, async_=True)
async def async_get_propagation_windows(hass: HomeAssistant) -> PropagationWindows:
    """Return the propagation windows, loading them on first use."""
    windows = PropagationWindows(hass)
    await windows.async_load()
    return windows


def _write_may_have_landed(err: HomeAssistantError) -> bool:
    """Return whether a failed pending dataset write may have reached the router.

    A refusal, a failed connect or a timeout before the write sent nothing;
    python-otbr-api reports a timed-out write as the unknown outcome.
    """
    cause = err.__cause__
    return isinstance(
        cause, python_otbr_api.PendingDatasetOutcomeUnknownError
    ) or not isinstance(
        cause,
        (python_otbr_api.OTBRError, aiohttp.ClientConnectorError, TimeoutError),
    )


async def _router_holds_a_pending_dataset(data: OTBRData) -> bool:
    """Return whether the router may be propagating a pending dataset.

    Assumed when it cannot be asked, or registers datasets with the leader
    and so holds no copy right after a write.
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
    """Return the lock serializing dataset writes across all config entries.

    Callers hold it across their read and write.
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
    """Handle OTBR errors, each pending dataset verdict as its own error."""

    @wraps(func)
    async def _func(self: OTBRData, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except python_otbr_api.PendingDatasetConflictError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pending_dataset_in_place",
            ) from exc
        except python_otbr_api.PendingDatasetRejectedError as exc:
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
    # Arms a look at a write this router was handed, once its delay has run out
    schedule_settlement: Callable[[int], None] | None = None

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
        """Set the pending operational dataset in TLVS format."""
        await self.api.set_pending_dataset_tlvs(dataset)

    async def set_channel(
        self,
        hass: HomeAssistant,
        channel: int,
        delay: float = PENDING_DATASET_DELAY_TIMER / 1000,
    ) -> None:
        """Change the channel with a pending dataset built from the active one.

        Refused while the network's window is open and through a router behind
        the stored dataset; stores the new dataset. Hold the dataset lock.
        """
        if not 11 <= channel <= 26:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_channel",
                translation_placeholders={"channel": str(channel)},
            )
        active_tlvs = await self.get_active_dataset_tlvs()
        if active_tlvs is None:
            # No active dataset: the library refuses.
            await self._set_channel(channel, delay)
            return
        active = parse_dataset(active_tlvs)
        if (xpan := active.get(MeshcopTLVType.EXTPANID)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="router_dataset_invalid"
            )
        extended_pan_id = str(xpan).lower()
        windows = await async_get_propagation_windows(hass)
        if remaining := windows.seconds_in_flight(extended_pan_id):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="dataset_propagating",
                translation_placeholders={"remaining": str(remaining)},
            )
        # A router behind the stored dataset missed a change.
        running = timestamp_parts(active, MeshcopTLVType.ACTIVETIMESTAMP)
        if any(
            timestamp_parts(entry.dataset, MeshcopTLVType.ACTIVETIMESTAMP) > running
            for entry in (await async_get_store(hass)).datasets.values()
            if entry.extended_pan_id.lower() == extended_pan_id
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="router_dataset_outdated"
            )
        moved, stamp = _on_channel(active, channel, windows.get(extended_pan_id))
        pending = dict(moved)
        pending[MeshcopTLVType.PENDINGTIMESTAMP] = tlv_parser.Timestamp.from_values(
            MeshcopTLVType.PENDINGTIMESTAMP, seconds=stamp[0], ticks=stamp[1]
        )
        pending[MeshcopTLVType.DELAYTIMER] = tlv_parser.DelayTimer.from_milliseconds(
            int(delay * 1000)
        )
        pending_tlvs = bytes.fromhex(tlv_parser.encode_tlv(pending))
        try:
            await windows.async_write(
                self,
                extended_pan_id,
                stamp,
                delay,
                lambda: self.set_pending_dataset_tlvs(pending_tlvs),
                migration=(
                    extended_pan_id,
                    self.entry_id,
                    tlv_parser.encode_tlv(moved),
                ),
            )
        except HomeAssistantError as err:
            if _write_may_have_landed(err):
                # Report the write's error, not a failed read.
                with suppress(HomeAssistantError):
                    await self._async_store_channel_change(
                        hass, windows, extended_pan_id, moved, False
                    )
                # Left unsettled, the change is looked at again after its delay.
                if self.schedule_settlement is not None and (
                    remaining := windows.seconds_until_landed(
                        extended_pan_id, self.entry_id
                    )
                ):
                    self.schedule_settlement(remaining)
            raise
        await self._async_store_channel_change(
            hass, windows, extended_pan_id, moved, True
        )

    @_handle_otbr_error
    async def _set_channel(self, channel: int, delay: float) -> None:
        await self.api.set_channel(channel, delay=int(delay * 1000))

    async def _async_store_channel_change(
        self,
        hass: HomeAssistant,
        windows: PropagationWindows,
        extended_pan_id: str,
        moved: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
        landed: bool,
    ) -> None:
        """Store the dataset the mesh moves to and write the store to disk.

        The router's copy when it holds one, else the dataset sent once the
        router answered. Until then it stays on the network's record, for the
        router found running it to settle. Raises when the store kept a
        dataset at least as new.
        """
        try:
            held = await self._async_dataset_held(moved)
        except HomeAssistantError:
            if not landed:
                raise
            # The router answered, so the write landed.
            held = None
        if held is None:
            if not landed:
                return
            held = moved
        result = await async_add_dataset(hass, DOMAIN, tlv_parser.encode_tlv(held))
        await (await async_get_store(hass)).async_save()
        await windows.async_settle(extended_pan_id)
        if result is DatasetAddResult.DISCARDED:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="dataset_discarded"
            )

    async def _async_dataset_held(
        self, moved: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]
    ) -> dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem] | None:
        """Return the router's copy of the change: pending, or active once applied.

        An active dataset stamped below the change is the one before it.
        """
        if (tlvs := await self.get_pending_dataset_tlvs()) is None:
            if (tlvs := await self.get_active_dataset_tlvs()) is None:
                return None
            dataset = parse_dataset(tlvs)
            if timestamp_parts(
                dataset, MeshcopTLVType.ACTIVETIMESTAMP
            ) < timestamp_parts(moved, MeshcopTLVType.ACTIVETIMESTAMP):
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
        config_entry_id=otbrdata.entry_id,
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
            config_entry_id=otbrdata.entry_id,
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
