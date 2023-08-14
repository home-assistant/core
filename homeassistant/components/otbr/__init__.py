"""The Open Thread Border Router integration."""
from __future__ import annotations

import asyncio
import contextlib

import aiohttp
import python_otbr_api

from homeassistant.components.thread import (
    async_add_dataset,
    async_get_preferred_border_agent_id,
    async_get_preferred_dataset,
    async_set_preferred_border_agent_id,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .util import OTBRData, update_issues

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Open Thread Border Router component."""
    websocket_api.async_setup(hass)
    if len(config_entries := hass.config_entries.async_entries(DOMAIN)):
        for config_entry in config_entries[1:]:
            await hass.config_entries.async_remove(config_entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Open Thread Border Router config entry."""
    api = python_otbr_api.OTBR(entry.data["url"], async_get_clientsession(hass), 10)

    otbrdata = OTBRData(entry.data["url"], api, entry.entry_id)
    try:
        dataset_tlvs = await otbrdata.get_active_dataset_tlvs()
    except (
        HomeAssistantError,
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ) as err:
        raise ConfigEntryNotReady("Unable to connect") from err
    if dataset_tlvs:
        await update_issues(hass, otbrdata, dataset_tlvs)
        await async_add_dataset(hass, DOMAIN, dataset_tlvs.hex())
        # If this OTBR's dataset is the preferred one, and there is no preferred router,
        # make this the preferred router
        border_agent_id: bytes | None = None
        with contextlib.suppress(
            HomeAssistantError, aiohttp.ClientError, asyncio.TimeoutError
        ):
            border_agent_id = await otbrdata.get_border_agent_id()
        if (
            await async_get_preferred_dataset(hass) == dataset_tlvs.hex()
            and await async_get_preferred_border_agent_id(hass) is None
            and border_agent_id
        ):
            await async_set_preferred_border_agent_id(hass, border_agent_id.hex())

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data[DOMAIN] = otbrdata

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """
    if DOMAIN not in hass.data:
        raise HomeAssistantError("OTBR API not available")

    data: OTBRData = hass.data[DOMAIN]
    return await data.get_active_dataset_tlvs()
