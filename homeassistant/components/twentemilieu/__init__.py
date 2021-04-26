"""Support for Twente Milieu."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from twentemilieu import TwenteMilieu
import voluptuous as vol

from homeassistant.components.twentemilieu.const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DATA_UPDATE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

SCAN_INTERVAL = timedelta(seconds=3600)

SERVICE_UPDATE = "update"
SERVICE_SCHEMA = vol.Schema({vol.Optional(CONF_ID): cv.string})


async def _update_twentemilieu(hass: HomeAssistant, unique_id: str | None) -> None:
    """Update Twente Milieu."""
    if unique_id is not None:
        twentemilieu = hass.data[DOMAIN].get(unique_id)
        if twentemilieu is not None:
            await twentemilieu.update()
            async_dispatcher_send(hass, DATA_UPDATE, unique_id)
    else:
        await asyncio.wait(
            [twentemilieu.update() for twentemilieu in hass.data[DOMAIN].values()]
        )

        for uid in hass.data[DOMAIN]:
            async_dispatcher_send(hass, DATA_UPDATE, uid)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Twente Milieu components."""

    async def update(call) -> None:
        """Service call to manually update the data."""
        unique_id = call.data.get(CONF_ID)
        await _update_twentemilieu(hass, unique_id)

    hass.services.async_register(DOMAIN, SERVICE_UPDATE, update, schema=SERVICE_SCHEMA)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twente Milieu from a config entry."""
    session = async_get_clientsession(hass)
    twentemilieu = TwenteMilieu(
        post_code=entry.data[CONF_POST_CODE],
        house_number=entry.data[CONF_HOUSE_NUMBER],
        house_letter=entry.data[CONF_HOUSE_LETTER],
        session=session,
    )

    unique_id = entry.data[CONF_ID]
    hass.data[DOMAIN][unique_id] = twentemilieu

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    async def _interval_update(now=None) -> None:
        """Update Twente Milieu data."""
        await _update_twentemilieu(hass, unique_id)

    async_track_time_interval(hass, _interval_update, SCAN_INTERVAL)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Twente Milieu config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    del hass.data[DOMAIN][entry.data[CONF_ID]]

    return True
