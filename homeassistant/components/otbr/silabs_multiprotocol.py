"""Silicon Labs Multiprotocol support."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import TYPE_CHECKING, Any, Concatenate

import aiohttp
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
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
) -> None:
    """Set the channel to be used.

    Does nothing if not configured.
    """
    await data.set_channel(channel, delay)

    # Import the new dataset
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
