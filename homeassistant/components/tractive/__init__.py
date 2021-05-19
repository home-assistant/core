"""The tractive integration."""
from __future__ import annotations

import asyncio
import logging

import aiotractive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, TRACKER_HARDWARE_STATUS_UPDATED, TRACKER_POSITION_UPDATED

PLATFORMS = ["device_tracker"]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    client = aiotractive.Tractive(data[CONF_USERNAME], data[CONF_PASSWORD])

    tractive = TractiveClient(hass, client)
    hass.data[DOMAIN][entry.entry_id] = tractive

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    await asyncio.sleep(5)
    tractive.subscribe()

    async def cancel_listen_task(_):
        await tractive.unsubscribe()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tractive = hass.data[DOMAIN].pop(entry.entry_id)
        await tractive.unsubscribe()
    return unload_ok


class TractiveClient:
    """A Tractive client."""

    def __init__(self, hass, client):
        """Initialize the client."""
        self._hass = hass
        self._client = client
        self._listen_task = None

    async def trackable_objects(self):
        """Get list of trackable objects."""
        return await self._client.trackable_objects()

    def tracker(self, id):
        """Get tracker by id."""
        return self._client.tracker(id)

    def subscribe(self):
        """Start event listener coroutine."""
        self._listen_task = asyncio.create_task(self._listen())

    async def unsubscribe(self):
        """Stop event listener coroutine."""
        if self._listen_task:
            self._listen_task.cancel()
        await self._client.close()

    async def _listen(self):
        async for event in self._client.events():
            if event["message"] != "tracker_status":
                continue

            _LOGGER.warning("Event received. Payload=%s", event)

            if "hardware" in event:
                self._send_hardware_update(event)

            if "position" in event:
                self._send_position_update(event)

    def _send_hardware_update(self, event):
        payload = {"battery_level": event["hardware"]["battery_level"]}
        self._dispatch_tracker_event(
            TRACKER_HARDWARE_STATUS_UPDATED, event["tracker_id"], payload
        )

    def _send_position_update(self, event):
        payload = {
            "latitude": event["position"]["latlong"][0],
            "longitude": event["position"]["latlong"][1],
            "accuracy": event["position"]["accuracy"],
        }
        self._dispatch_tracker_event(
            TRACKER_POSITION_UPDATED, event["tracker_id"], payload
        )

    def _dispatch_tracker_event(self, event_name, tracker_id, payload):
        _LOGGER.warning(
            "Dispatching event %s-%s payload=%s", event_name, tracker_id, payload
        )
        async_dispatcher_send(
            self._hass,
            f"{event_name}-{tracker_id}",
            payload,
        )
