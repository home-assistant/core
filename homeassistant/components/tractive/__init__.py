"""The tractive integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, cast

import aiotractive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_EMAIL,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_BUZZER,
    ATTR_CALORIES,
    ATTR_DAILY_GOAL,
    ATTR_LED,
    ATTR_LIVE_TRACKING,
    ATTR_MINUTES_ACTIVE,
    ATTR_MINUTES_DAY_SLEEP,
    ATTR_MINUTES_NIGHT_SLEEP,
    ATTR_MINUTES_REST,
    ATTR_TRACKER_STATE,
    CLIENT,
    CLIENT_ID,
    DOMAIN,
    RECONNECT_INTERVAL,
    SERVER_UNAVAILABLE,
    TRACKABLES,
    TRACKER_ACTIVITY_STATUS_UPDATED,
    TRACKER_HARDWARE_STATUS_UPDATED,
    TRACKER_POSITION_UPDATED,
    TRACKER_WELLNESS_STATUS_UPDATED,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
]


_LOGGER = logging.getLogger(__name__)


@dataclass
class Trackables:
    """A class that describes trackables."""

    tracker: aiotractive.tracker.Tracker
    trackable: dict
    tracker_details: dict
    hw_info: dict
    pos_report: dict


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    data = entry.data

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = aiotractive.Tractive(
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        client_id=CLIENT_ID,
    )
    try:
        creds = await client.authenticate()
    except aiotractive.exceptions.UnauthorizedError as error:
        await client.close()
        raise ConfigEntryAuthFailed from error
    except aiotractive.exceptions.TractiveError as error:
        await client.close()
        raise ConfigEntryNotReady from error

    tractive = TractiveClient(hass, client, creds["user_id"], entry)

    try:
        trackable_objects = await client.trackable_objects()
        trackables = await asyncio.gather(
            *(_generate_trackables(client, item) for item in trackable_objects)
        )
    except aiotractive.exceptions.TractiveError as error:
        raise ConfigEntryNotReady from error

    # When the pet defined in Tractive has no tracker linked we get None as `trackable`.
    # So we have to remove None values from trackables list.
    trackables = [item for item in trackables if item]

    hass.data[DOMAIN][entry.entry_id][CLIENT] = tractive
    hass.data[DOMAIN][entry.entry_id][TRACKABLES] = trackables

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def cancel_listen_task(_: Event) -> None:
        await tractive.unsubscribe()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)
    )

    return True


async def _generate_trackables(
    client: aiotractive.Tractive,
    trackable: aiotractive.trackable_object.TrackableObject,
) -> Trackables | None:
    """Generate trackables."""
    trackable = await trackable.details()

    # Check that the pet has tracker linked.
    if not trackable["device_id"]:
        return None

    tracker = client.tracker(trackable["device_id"])

    tracker_details, hw_info, pos_report = await asyncio.gather(
        tracker.details(), tracker.hw_info(), tracker.pos_report()
    )

    return Trackables(tracker, trackable, tracker_details, hw_info, pos_report)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tractive = hass.data[DOMAIN][entry.entry_id].pop(CLIENT)
        await tractive.unsubscribe()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class TractiveClient:
    """A Tractive client."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: aiotractive.Tractive,
        user_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the client."""
        self._hass = hass
        self._client = client
        self._user_id = user_id
        self._last_hw_time = 0
        self._last_pos_time = 0
        self._listen_task: asyncio.Task | None = None
        self._config_entry = config_entry

    @property
    def user_id(self) -> str:
        """Return user id."""
        return self._user_id

    @property
    def subscribed(self) -> bool:
        """Return True if subscribed."""
        if self._listen_task is None:
            return False

        if self._listen_task.cancelled is True:
            return False

        return True

    async def trackable_objects(
        self,
    ) -> list[aiotractive.trackable_object.TrackableObject]:
        """Get list of trackable objects."""
        return cast(
            list[aiotractive.trackable_object.TrackableObject],
            await self._client.trackable_objects(),
        )

    def tracker(self, tracker_id: str) -> aiotractive.tracker.Tracker:
        """Get tracker by id."""
        return self._client.tracker(tracker_id)

    def subscribe(self) -> None:
        """Start event listener coroutine."""
        self._listen_task = asyncio.create_task(self._listen())

    async def unsubscribe(self) -> None:
        """Stop event listener coroutine."""
        if self._listen_task:
            self._listen_task.cancel()
        await self._client.close()

    async def _listen(self) -> None:
        server_was_unavailable = False
        while True:
            try:
                async for event in self._client.events():
                    if server_was_unavailable:
                        _LOGGER.debug("Tractive is back online")
                        server_was_unavailable = False
                    if event["message"] == "activity_update":
                        self._send_activity_update(event)
                        continue
                    if event["message"] == "wellness_overview":
                        self._send_wellness_update(event)
                        continue
                    if (
                        "hardware" in event
                        and self._last_hw_time != event["hardware"]["time"]
                    ):
                        self._last_hw_time = event["hardware"]["time"]
                        self._send_hardware_update(event)

                    if (
                        "position" in event
                        and self._last_pos_time != event["position"]["time"]
                    ):
                        self._last_pos_time = event["position"]["time"]
                        self._send_position_update(event)
            except aiotractive.exceptions.UnauthorizedError:
                self._config_entry.async_start_reauth(self._hass)
                await self.unsubscribe()
                _LOGGER.error(
                    "Authentication failed for %s, try reconfiguring device",
                    self._config_entry.data[CONF_EMAIL],
                )
                return

            except aiotractive.exceptions.TractiveError:
                _LOGGER.debug(
                    (
                        "Tractive is not available. Internet connection is down?"
                        " Sleeping %i seconds and retrying"
                    ),
                    RECONNECT_INTERVAL.total_seconds(),
                )
                self._last_hw_time = 0
                self._last_pos_time = 0
                async_dispatcher_send(
                    self._hass, f"{SERVER_UNAVAILABLE}-{self._user_id}"
                )
                await asyncio.sleep(RECONNECT_INTERVAL.total_seconds())
                server_was_unavailable = True
                continue

    def _send_hardware_update(self, event: dict[str, Any]) -> None:
        # Sometimes hardware event doesn't contain complete data.
        payload = {
            ATTR_BATTERY_LEVEL: event["hardware"]["battery_level"],
            ATTR_TRACKER_STATE: event["tracker_state"].lower(),
            ATTR_BATTERY_CHARGING: event["charging_state"] == "CHARGING",
            ATTR_LIVE_TRACKING: event.get("live_tracking", {}).get("active"),
            ATTR_BUZZER: event.get("buzzer_control", {}).get("active"),
            ATTR_LED: event.get("led_control", {}).get("active"),
        }
        self._dispatch_tracker_event(
            TRACKER_HARDWARE_STATUS_UPDATED, event["tracker_id"], payload
        )

    def _send_activity_update(self, event: dict[str, Any]) -> None:
        payload = {
            ATTR_MINUTES_ACTIVE: event["progress"]["achieved_minutes"],
            ATTR_DAILY_GOAL: event["progress"]["goal_minutes"],
        }
        self._dispatch_tracker_event(
            TRACKER_ACTIVITY_STATUS_UPDATED, event["pet_id"], payload
        )

    def _send_wellness_update(self, event: dict[str, Any]) -> None:
        payload = {
            ATTR_CALORIES: event["activity"]["calories"],
            ATTR_MINUTES_DAY_SLEEP: event["sleep"]["minutes_day_sleep"],
            ATTR_MINUTES_NIGHT_SLEEP: event["sleep"]["minutes_night_sleep"],
            ATTR_MINUTES_REST: event["activity"]["minutes_rest"],
        }
        self._dispatch_tracker_event(
            TRACKER_WELLNESS_STATUS_UPDATED, event["pet_id"], payload
        )

    def _send_position_update(self, event: dict[str, Any]) -> None:
        payload = {
            "latitude": event["position"]["latlong"][0],
            "longitude": event["position"]["latlong"][1],
            "accuracy": event["position"]["accuracy"],
            "sensor_used": event["position"]["sensor_used"],
        }
        self._dispatch_tracker_event(
            TRACKER_POSITION_UPDATED, event["tracker_id"], payload
        )

    def _dispatch_tracker_event(
        self, event_name: str, tracker_id: str, payload: dict[str, Any]
    ) -> None:
        async_dispatcher_send(
            self._hass,
            f"{event_name}-{tracker_id}",
            payload,
        )
