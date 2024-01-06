"""Silicon Labs Multiprotocol support."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.components.thread import async_add_dataset
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import DOMAIN
from .util import OTBRData

_LOGGER = logging.getLogger(__name__)


async def async_change_channel(hass: HomeAssistant, channel: int, delay: float) -> None:
    """Set the channel to be used.

    Does nothing if not configured.
    """
    if DOMAIN not in hass.data:
        return

    data: OTBRData = hass.data[DOMAIN]
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


async def async_get_channel(hass: HomeAssistant) -> int | None:
    """Return the channel.

    Returns None if not configured.
    """
    if DOMAIN not in hass.data:
        return None

    data: OTBRData = hass.data[DOMAIN]

    try:
        dataset = await data.get_active_dataset()
    except (
        HomeAssistantError,
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ) as err:
        _LOGGER.warning("Failed to communicate with OTBR %s", err)
        return None

    if dataset is None:
        return None

    return dataset.channel


async def async_using_multipan(hass: HomeAssistant) -> bool:
    """Return if the multiprotocol device is used.

    Returns False if not configured.
    """
    if DOMAIN not in hass.data:
        return False

    data: OTBRData = hass.data[DOMAIN]
    return is_multiprotocol_url(data.url)
