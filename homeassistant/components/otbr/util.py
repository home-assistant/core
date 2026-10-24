"""Utility functions for the Open Thread Border Router integration."""

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import dataclasses
from functools import wraps
import logging
import math
import random
from typing import TYPE_CHECKING, Any, Concatenate, cast

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
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], channel: int
) -> tuple[dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], tuple[int, int]]:
    """Return the active dataset moved to a channel, and its new timestamp.

    Stamped as python-otbr-api stamps a channel change: one second up.
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
    """Per network, until when a pending dataset sent from here propagates.

    Kept on disk and across routers: one that has not learned a pending
    dataset yet would accept a second one superseding it.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the record."""
        self._store = Store[dict[str, float]](
            hass,
            PROPAGATION_WINDOWS_STORAGE_VERSION,
            PROPAGATION_WINDOWS_STORAGE_KEY,
            # A restart mid-write must not truncate the record.
            atomic_writes=True,
        )
        self._until: dict[str, float] = {}

    async def async_load(self) -> None:
        """Load the recorded windows."""
        if data := await self._store.async_load():
            self._until = data

    def seconds_left(self, extended_pan_id: str) -> int:
        """Return the seconds a network's window has left, zero when none is open."""
        return _seconds_left(self._until.get(extended_pan_id, 0))

    async def async_write(
        self,
        data: OTBRData,
        extended_pan_id: str,
        delay: float,
        write: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Run a pending dataset write inside the window it opens on the mesh.

        Opened before the write, wide enough to cover the write itself; then
        set to the delay from the router's answer, or handed back if nothing
        was written.
        """
        previous = self._until.get(extended_pan_id)

        async def set_until(until: float | None) -> None:
            if until is None:
                self._until.pop(extended_pan_id, None)
            else:
                self._until[extended_pan_id] = until
            await self._store.async_save(self._until)

        await set_until(dt_util.utcnow().timestamp() + delay + _WRITE_WINDOW_S)
        try:
            await write()
        except HomeAssistantError as err:
            if not _write_may_have_landed(err):
                in_flight = False
            elif isinstance(
                err.__cause__, python_otbr_api.PendingDatasetOutcomeUnknownError
            ):
                # The leader did not answer: it may be propagating.
                in_flight = True
            else:
                # The connection dropped: ask the router.
                in_flight = await _router_holds_a_pending_dataset(data)
            if in_flight:
                # Measured from the latest moment the write can have landed.
                await set_until(dt_util.utcnow().timestamp() + delay)
            else:
                await set_until(previous)
            raise
        # Counted from the router's answer, not from the request.
        await set_until(dt_util.utcnow().timestamp() + delay)


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
        if remaining := windows.seconds_left(extended_pan_id):
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
        moved, stamp = _on_channel(active, channel)
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
                delay,
                lambda: self.set_pending_dataset_tlvs(pending_tlvs),
            )
        except HomeAssistantError as err:
            if _write_may_have_landed(err):
                # Report the write's error, not a failed read.
                with suppress(HomeAssistantError):
                    await self._async_store_channel_change(hass, moved, False)
            raise
        await self._async_store_channel_change(hass, moved, True)

    @_handle_otbr_error
    async def _set_channel(self, channel: int, delay: float) -> None:
        await self.api.set_channel(channel, delay=int(delay * 1000))

    async def _async_store_channel_change(
        self,
        hass: HomeAssistant,
        moved: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
        landed: bool,
    ) -> None:
        """Store the dataset the mesh moves to and write the store to disk.

        The router's copy when it holds one, else the dataset sent once the
        router answered. Raises when the store kept a dataset at least as new.
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
