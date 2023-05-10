"""Silicon Labs Multiprotocol support."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import DOMAIN
from .util import OTBRData

_LOGGER = logging.getLogger(__name__)


async def async_change_channel(hass: HomeAssistant, channel: int) -> None:
    """Set the channel to be used.

    Does nothing if not configured.
    """
    if DOMAIN not in hass.data:
        return

    data: OTBRData = hass.data[DOMAIN]
    await data.set_channel(channel)


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
