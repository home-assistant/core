"""Silicon Labs Multiprotocol support."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import TYPE_CHECKING, Any, Concatenate

import aiohttp
from python_otbr_api import OTBRError, PendingDatasetOutcomeUnknownError, tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    ChannelChangeOutcomeUnknownError,
    is_multiprotocol_url,
)
from homeassistant.components.thread import async_add_dataset
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .util import OTBRData

if TYPE_CHECKING:
    from . import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)

# Reads of the pending dataset after a write without an answer: a router that
# answered late is often reachable again a moment later.
_RECONCILE_ATTEMPTS = 3
_RECONCILE_INTERVAL_S = 2


def async_get_otbr_data[**_P, _R, _R_Def](
    retval: _R_Def,
) -> Callable[
    [Callable[Concatenate[HomeAssistant, OTBRData, _P], Coroutine[Any, Any, _R]]],
    Callable[Concatenate[HomeAssistant, _P], Coroutine[Any, Any, _R | _R_Def]],
]:
    """Decorate function to get OTBR data."""

    def _async_get_otbr_data(
        orig_func: Callable[
            Concatenate[HomeAssistant, OTBRData, _P],
            Coroutine[Any, Any, _R],
        ],
    ) -> Callable[Concatenate[HomeAssistant, _P], Coroutine[Any, Any, _R | _R_Def]]:
        """Decorate function to get OTBR data."""

        @wraps(orig_func)
        async def async_get_otbr_data_wrapper(
            hass: HomeAssistant, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R | _R_Def:
            """Fetch OTBR data and pass to orig_func."""
            config_entry: OTBRConfigEntry
            for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
                data = config_entry.runtime_data
                if is_multiprotocol_url(data.url):
                    return await orig_func(hass, data, *args, **kwargs)

            return retval

        return async_get_otbr_data_wrapper

    return _async_get_otbr_data


@async_get_otbr_data(None)
async def async_change_channel(
    hass: HomeAssistant,
    data: OTBRData,
    channel: int,
    delay: float,
) -> asyncio.Task[None]:
    """Set the channel to be used.

    Does nothing if not configured. Raises only when the router refused the
    change, with the reason it gave; the dataset the mesh moves to is imported
    in the returned task, since the change is under way whether that import
    succeeds or not.
    """
    try:
        await data.set_channel(channel, delay)
    except HomeAssistantError as err:
        cause = err.__cause__
        if isinstance(cause, (aiohttp.ClientConnectorError, TimeoutError)) or (
            isinstance(cause, OTBRError)
            and not isinstance(cause, PendingDatasetOutcomeUnknownError)
        ):
            # Refused, never connected, or timed out before the write (the
            # library reports a timeout of the write itself as an unknown
            # outcome): nothing was written. The router's reason, not the
            # wrapper's generic text.
            raise HomeAssistantError(
                str(cause) if isinstance(cause, OTBRError) else str(err)
            ) from err
        # No answer from the leader, or the connection dropped with the
        # request out. The router holding the pending dataset shows the
        # change is on its way regardless; holding another, or none, it is not.
        try:
            held = await _async_holds_channel_change(data, channel)
        except HomeAssistantError as read_err:
            raise ChannelChangeOutcomeUnknownError(
                "the border router could not be read after the write, so whether "
                "the channel change went through is unknown"
            ) from read_err
        if not held:
            raise HomeAssistantError(
                "the border router did not confirm the channel change and holds "
                "no pending dataset for it"
            ) from err
    return hass.async_create_task(_async_import_dataset(hass, data))


async def _async_holds_channel_change(data: OTBRData, channel: int) -> bool:
    """Return whether the router holds a pending dataset moving to the channel.

    A pending dataset for another channel is another writer's, whose conflict
    answer an unanswered write may have lost.
    """
    if (tlvs := await _async_pending_dataset(data)) is None:
        return False
    try:
        item = tlv_parser.parse_tlv(tlvs.hex()).get(MeshcopTLVType.CHANNEL)
    except tlv_parser.TLVError:
        return False
    return isinstance(item, tlv_parser.Channel) and item.channel == channel


async def _async_pending_dataset(data: OTBRData) -> bytes | None:
    """Read the router's pending dataset, trying again for a few seconds."""
    attempts = _RECONCILE_ATTEMPTS
    while True:
        try:
            return await data.get_pending_dataset_tlvs()
        except HomeAssistantError:
            attempts -= 1
            if not attempts:
                raise
        await asyncio.sleep(_RECONCILE_INTERVAL_S)


async def _async_import_dataset(hass: HomeAssistant, data: OTBRData) -> None:
    """Import the dataset a channel change moves the mesh to."""
    dataset_tlvs = await data.get_pending_dataset_tlvs()
    if dataset_tlvs is None:
        # The activation timer may have expired already
        dataset_tlvs = await data.get_active_dataset_tlvs()
    if dataset_tlvs is None:
        # Don't try to import a None dataset
        return

    dataset = tlv_parser.parse_tlv(dataset_tlvs.hex())
    dataset.pop(MeshcopTLVType.DELAYTIMER, None)
    dataset.pop(MeshcopTLVType.PENDINGTIMESTAMP, None)
    dataset_tlvs_str = tlv_parser.encode_tlv(dataset)
    await async_add_dataset(hass, DOMAIN, dataset_tlvs_str)


@async_get_otbr_data(None)
async def async_get_channel(hass: HomeAssistant, data: OTBRData) -> int | None:
    """Return the channel.

    Returns None if not configured.
    """
    try:
        dataset = await data.get_active_dataset()
    except (
        HomeAssistantError,
        aiohttp.ClientError,
        TimeoutError,
    ) as err:
        _LOGGER.warning("Failed to communicate with OTBR %s", err)
        return None

    if dataset is None:
        return None

    return dataset.channel


@async_get_otbr_data(False)
async def async_using_multipan(hass: HomeAssistant, data: OTBRData) -> bool:
    """Return if the multiprotocol device is used.

    Returns False if not configured.
    """
    return True
