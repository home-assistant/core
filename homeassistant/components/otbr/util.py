"""Utility functions for the Open Thread Border Router integration."""

import asyncio
from collections.abc import Callable, Coroutine
import dataclasses
from functools import wraps
import logging
import random
from typing import TYPE_CHECKING, Any, Concatenate, cast

import aiohttp
import python_otbr_api
from python_otbr_api import PENDING_DATASET_DELAY_TIMER, tlv_parser
from python_otbr_api.pskc import compute_pskc
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    MultiprotocolAddonManager,
    get_multiprotocol_addon_manager,
    is_multiprotocol_url,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from . import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)


DATASET_LOCK_KEY: HassKey[asyncio.Lock] = HassKey("otbr_dataset_lock")
ISSUED_TIMESTAMPS_KEY: HassKey[IssuedTimestamps] = HassKey("otbr_issued_timestamps")
ISSUED_TIMESTAMPS_STORAGE_KEY = f"{DOMAIN}.issued_timestamps"
ISSUED_TIMESTAMPS_STORAGE_VERSION = 1


class IssuedTimestamps:
    """The newest timestamp this integration has issued, per source network.

    Keyed by extended PAN ID: a busy network must not raise the floor for the
    others, which would eventually exhaust their timestamps too.

    Kept on disk, not only in memory: a pending dataset takes its delay to
    reach every router on the mesh, and a restart inside that window must not
    let the next migration hand out the stamp again.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the record."""
        self._store = Store[dict[str, list[int]]](
            hass,
            ISSUED_TIMESTAMPS_STORAGE_VERSION,
            ISSUED_TIMESTAMPS_STORAGE_KEY,
            # This file exists to survive an ill-timed restart; the same
            # restart must not be able to truncate an in-place rewrite.
            atomic_writes=True,
        )
        self._issued: dict[str, tuple[int, int]] = {}

    async def async_load(self) -> None:
        """Load what was issued before the last restart."""
        if data := await self._store.async_load():
            self._issued = {
                xpan: (seconds, ticks) for xpan, (seconds, ticks) in data.items()
            }

    def get(self, extended_pan_id: str) -> tuple[int, int]:
        """Return the newest timestamp issued for a network."""
        return self._issued.get(extended_pan_id, (0, 0))

    async def async_set(self, extended_pan_id: str, timestamp: tuple[int, int]) -> None:
        """Record a timestamp about to be issued for a network.

        Written through before the caller hands the dataset to the router:
        delaying the save would reopen the window this record exists to close.
        """
        self._issued[extended_pan_id] = timestamp
        await self._store.async_save(
            {xpan: list(stamp) for xpan, stamp in self._issued.items()}
        )


async def async_get_issued_timestamps(hass: HomeAssistant) -> IssuedTimestamps:
    """Return the record of issued timestamps, loading it on first use."""
    if (issued := hass.data.get(ISSUED_TIMESTAMPS_KEY)) is None:
        issued = IssuedTimestamps(hass)
        await issued.async_load()
        hass.data[ISSUED_TIMESTAMPS_KEY] = issued
    return issued


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
    """Handle OTBR errors."""

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

        Refused while a pending dataset is in place; the wrapper turns that
        refusal into the error that says so.
        """
        await self.api.set_pending_dataset_tlvs(dataset)

    @_handle_otbr_error
    async def set_channel(
        self, channel: int, delay: float = PENDING_DATASET_DELAY_TIMER / 1000
    ) -> None:
        """Set current channel."""
        await self.api.set_channel(channel, delay=int(delay * 1000))

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
