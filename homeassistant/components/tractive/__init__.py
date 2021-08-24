"""The tractive integration."""
from __future__ import annotations

import asyncio
import logging

import aiotractive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_EMAIL,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_DAILY_GOAL,
    ATTR_LIVE_TRACKING_REMAINING,
    ATTR_MINUTES_ACTIVE,
    ATTR_TRACKER_STATE,
    DOMAIN,
    RECONNECT_INTERVAL,
    SERVER_UNAVAILABLE,
    TRACKER_ACTIVITY_STATUS_UPDATED,
    TRACKER_HARDWARE_STATUS_UPDATED,
    TRACKER_POSITION_UPDATED,
)

PLATFORMS = ["device_tracker", "sensor"]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    data = entry.data

    hass.data.setdefault(DOMAIN, {})

    client = aiotractive.Tractive(
        data[CONF_EMAIL], data[CONF_PASSWORD], session=async_get_clientsession(hass)
    )
    try:
        creds = await client.authenticate()
    except aiotractive.exceptions.UnauthorizedError as error:
        await client.close()
        raise ConfigEntryAuthFailed from error
    except aiotractive.exceptions.TractiveError as error:
        await client.close()
        raise ConfigEntryNotReady from error

    tractive = TractiveClient(hass, client, creds["user_id"])
    tractive.subscribe()

    hass.data[DOMAIN][entry.entry_id] = tractive

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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

    def __init__(self, hass, client, user_id):
        """Initialize the client."""
        self._hass = hass
        self._client = client
        self._user_id = user_id
        self._listen_task = None
        self._last_hw_time = 0
        self._last_pos_time = 0

    @property
    def user_id(self):
        """Return user id."""
        return self._user_id

    async def trackable_objects(self):
        """Get list of trackable objects."""
        return await self._client.trackable_objects()

    def tracker(self, tracker_id):
        """Get tracker by id."""
        return self._client.tracker(tracker_id)

    def subscribe(self):
        """Start event listener coroutine."""
        self._listen_task = asyncio.create_task(self._listen())

    async def unsubscribe(self):
        """Stop event listener coroutine."""
        if self._listen_task:
            self._listen_task.cancel()
        await self._client.close()

    async def _listen(self):
        server_was_unavailable = False
        while True:
            try:
                async for event in self._client.events():
                    if server_was_unavailable:
                        _LOGGER.debug("Tractive is back online")
                        server_was_unavailable = False

                    if event["message"] == "activity_update":
                        self._send_activity_update(event)
                    else:
                        if "hardware" in event and self._last_hw_time != event[
                            "hardware"
                        ].get("time"):
                            self._last_hw_time = event["hardware"]["time"]
                            self._send_hardware_update(event)

                        if "position" in event and self._last_pos_time != event[
                            "position"
                        ].get("time"):
                            self._last_pos_time = event["position"]["time"]
                            self._send_position_update(event)
            except aiotractive.exceptions.TractiveError:
                _LOGGER.debug(
                    "Tractive is not available. Internet connection is down? Sleeping %i seconds and retrying",
                    RECONNECT_INTERVAL.total_seconds(),
                )
                async_dispatcher_send(
                    self._hass, f"{SERVER_UNAVAILABLE}-{self._user_id}"
                )
                await asyncio.sleep(RECONNECT_INTERVAL.total_seconds())
                server_was_unavailable = True
                continue

    def _send_hardware_update(self, event):
        payload = {
            ATTR_BATTERY_LEVEL: event["hardware"]["battery_level"],
            ATTR_LIVE_TRACKING_REMAINING: event.get("live_tracking", {}).get(
                "remaining"
            ),
            ATTR_TRACKER_STATE: event.get("tracker_state"),
        }
        self._dispatch_tracker_event(
            TRACKER_HARDWARE_STATUS_UPDATED, event["tracker_id"], payload
        )

    def _send_activity_update(self, event):
        payload = {
            ATTR_MINUTES_ACTIVE: event["progress"]["achieved_minutes"],
            ATTR_DAILY_GOAL: event["progress"]["goal_minutes"],
        }
        self._dispatch_tracker_event(
            TRACKER_ACTIVITY_STATUS_UPDATED, event["pet_id"], payload
        )

    def _send_position_update(self, event):
        payload = {
            "latitude": event["position"]["latlong"][0],
            "longitude": event["position"]["latlong"][1],
            "accuracy": event["position"]["accuracy"],
            "sensor_used": event["position"]["sensor_used"],
        }
        self._dispatch_tracker_event(
            TRACKER_POSITION_UPDATED, event["tracker_id"], payload
        )

    def _dispatch_tracker_event(self, event_name, tracker_id, payload):
        async_dispatcher_send(
            self._hass,
            f"{event_name}-{tracker_id}",
            payload,
        )
