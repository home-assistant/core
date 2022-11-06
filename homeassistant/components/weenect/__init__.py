"""The Weenect integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
from typing import Any

from _collections_abc import Callable
from aioweenect import AioWeenect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, TRACKER_ADDED, TRACKER_REMOVED

PLATFORMS = [
    Platform.DEVICE_TRACKER,
]

_LOGGER: logging.Logger = logging.getLogger(__name__)

DEFAULT_UPDATE_RATE = 30

DURATION_PATTERN = re.compile(r"\d\d[S,M,H]")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    client = AioWeenect(username=username, password=password, session=session)

    coordinator = WeenectDataUpdateCoordinator(hass, config_entry=entry, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(async_reload_entry)
    return True


class WeenectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, client: AioWeenect
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
        )
        self.client = client
        self.config_entry = config_entry
        self.unsub_dispatchers: list[Callable[[], None]] = []
        self.data: dict[int, Any] = {}

    async def _async_update_data(self) -> dict[int, Any]:
        """Update data via library."""
        try:
            data = await self.client.get_trackers()
            data = self.transform_data(data)
            self._detect_added_and_removed_trackers(data)
            self._adjust_update_rate(data)
            return data
        except Exception as exception:
            raise UpdateFailed(exception) from exception

    def _detect_added_and_removed_trackers(self, data: dict[int, Any]) -> None:
        """Detect if trackers were added or removed."""
        assert self.config_entry is not None
        added = data.keys() - self.data.keys()
        async_dispatcher_send(
            self.hass, f"{self.config_entry.entry_id}_{TRACKER_ADDED}", added
        )
        removed = self.data.keys() - data.keys()
        async_dispatcher_send(
            self.hass, f"{self.config_entry.entry_id}_{TRACKER_REMOVED}", removed
        )

    def _adjust_update_rate(self, data: dict[int, Any]) -> None:
        """Set the update rate to the shortest update rate of all trackers."""
        update_rate = timedelta(seconds=DEFAULT_UPDATE_RATE)
        for tracker in data.values():
            tracker_rate = self.parse_duration(tracker["last_freq_mode"])
            if tracker_rate and tracker_rate < update_rate:
                update_rate = tracker_rate
        self.update_interval = update_rate
        _LOGGER.debug("Setting update_interval to %s", update_rate)

    @staticmethod
    def transform_data(data: Any) -> dict[int, Any]:
        """Extract trackers from list and put them in a dict by tracker id."""
        result = {}
        for tracker in data["items"]:
            result[tracker["id"]] = tracker
        return result

    @staticmethod
    def parse_duration(duration: str) -> timedelta | None:
        """Parse a timedelta from a weenect duration."""
        if DURATION_PATTERN.match(duration) is not None:
            if duration.endswith("S"):
                return timedelta(seconds=float(duration[:-1]))
            if duration.endswith("M"):
                return timedelta(minutes=float(duration[:-1]))
            if duration.endswith("H"):
                return timedelta(hours=float(duration[:-1]))
        return None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    for unsub_dispatcher in hass.data[DOMAIN][entry.entry_id].unsub_dispatchers:
        unsub_dispatcher()
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
