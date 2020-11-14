"""Reolink integration for HomeAssistant."""
import asyncio
from datetime import timedelta
import logging
import re

import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .base import ReolinkBase
from .const import BASE, COORDINATOR, DOMAIN, EVENT_DATA_RECEIVED

SCAN_INTERVAL = timedelta(minutes=1)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera", "switch", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict): #pylint: disable=unused-argument
    """Set up the Reolink component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reolink from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    base = ReolinkBase(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    if not await base.connect_api():
        return False

    webhook_id = await register_webhook(hass, base.event_id)
    webhook_url = hass.components.webhook.async_generate_url(webhook_id)
    await base.subscribe(webhook_url)

    hass.data[DOMAIN][entry.entry_id] = {BASE: base}

    async def async_update_data():
        """Perform the actual updates."""

        async with async_timeout.timeout(10):
            await base.renew()
            await base.update_api()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="reolink",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, base.stop())

    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Reolink for inbound messages and calls."""

    _LOGGER.debug("Reolink webhook triggered")

    if not request.body_exists:
        _LOGGER.error("Webhook triggered without payload")

    data = await request.text()
    if not data:
        _LOGGER.error("Webhook triggered with unknown payload")
        return

    matches = re.findall(r'Name="IsMotion" Value="(.+?)"', data)
    if matches:
        is_motion = matches[0] == "true"
    else:
        _LOGGER.error("Webhook triggered with unknown payload")
        return

    _LOGGER.debug(data)

    handlers = hass.data["webhook"]

    for wid, info in handlers.items():
        _LOGGER.debug(info)

        if wid == webhook_id:
            event_id = info["name"]
            hass.bus.async_fire(event_id, {"IsMotion": is_motion})


async def register_webhook(hass, event_id):
    """Register a webhook for motion events."""
    webhook_id = hass.components.webhook.async_generate_id()

    hass.components.webhook.async_register(DOMAIN, event_id, webhook_id, handle_webhook)

    return webhook_id


async def unregister_webhook(hass: HomeAssistant, entry: ConfigEntry):
    """Unregister the webhook for motion events."""
    base = hass.data[DOMAIN][entry.entry_id][BASE]
    event_id = f"{EVENT_DATA_RECEIVED}-{base.api.mac_address.replace(':', '')}"

    handlers = hass.data["webhook"]

    for eid, info in handlers.items():
        if eid == event_id:
            _LOGGER.info("Unregistering webhook %s", info.name)
            hass.components.webhook.async_unregister(event_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    await unregister_webhook(hass, entry)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
