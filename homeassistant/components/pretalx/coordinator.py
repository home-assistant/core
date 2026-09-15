"""DataUpdateCoordinator for the pretalx integration."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, override

from aiohttp import ClientError, ClientResponseError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EVENT, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
PAGE_SIZE = 100

type PretalxConfigEntry = ConfigEntry[PretalxCoordinator]


class PretalxError(Exception):
    """Base error for the pretalx client."""


class PretalxEventNotFound(PretalxError):
    """Raised when the requested event does not exist."""


@dataclass
class PretalxRoom:
    """A room at a pretalx event."""

    room_id: int
    name: str


@dataclass
class PretalxSession:
    """A scheduled talk in a single room."""

    uid: str
    title: str
    start: datetime
    end: datetime
    room_name: str
    description: str | None


@dataclass
class PretalxData:
    """Data fetched for a pretalx event."""

    event_name: str
    rooms: dict[int, PretalxRoom]
    sessions: dict[int, list[PretalxSession]]


def _localized(value: dict[str, str], locale: str | None) -> str:
    """Return a plain string from a localized pretalx field."""
    if locale and locale in value:
        return value[locale]
    return next(iter(value.values()), "")


def _build_description(speakers: list[str], abstract: str) -> str | None:
    """Combine speaker names and the abstract into a description."""
    parts = []
    if speakers:
        parts.append(", ".join(speakers))
    if abstract:
        parts.append(abstract)
    return "\n\n".join(parts) or None


class PretalxClient:
    """Thin async client for the public pretalx REST API."""

    def __init__(self, session: ClientSession, url: str, event: str) -> None:
        """Initialize the client."""
        self._session = session
        self._base = f"{url.rstrip('/')}/api/events/{event}"

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a single GET request and return the decoded JSON."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.get(url, params=params)
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as err:
            if err.status == 404:
                raise PretalxEventNotFound(str(err)) from err
            raise PretalxError(str(err) or type(err).__name__) from err
        except (TimeoutError, ClientError) as err:
            raise PretalxError(str(err) or type(err).__name__) from err

    async def _get_paginated(
        self, path: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return all results of a paginated endpoint."""
        results: list[dict[str, Any]] = []
        url: str | None = f"{self._base}{path}"
        page_params: dict[str, Any] | None = {**params, "limit": PAGE_SIZE}
        while url:
            data = await self._get(url, page_params)
            results.extend(data["results"])
            # Subsequent pages are addressed by an absolute URL that already
            # carries the query parameters.
            url = data.get("next")
            page_params = None
        return results

    async def async_get_event(self) -> dict[str, Any]:
        """Return the event details."""
        return await self._get(f"{self._base}/")

    async def async_get_rooms(self) -> list[dict[str, Any]]:
        """Return the rooms of the event."""
        return await self._get_paginated("/rooms/", {})

    async def async_get_talks(self) -> list[dict[str, Any]]:
        """Return the confirmed talks with their scheduled slots."""
        return await self._get_paginated(
            "/submissions/",
            {"state": "confirmed", "expand": "slots.room,speakers"},
        )


class PretalxCoordinator(DataUpdateCoordinator[PretalxData]):
    """Coordinator that fetches the pretalx schedule."""

    config_entry: PretalxConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: PretalxConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.client = PretalxClient(
            async_get_clientsession(hass),
            config_entry.data[CONF_URL],
            config_entry.data[CONF_EVENT],
        )

    @override
    async def _async_update_data(self) -> PretalxData:
        """Fetch the event, rooms and schedule."""
        try:
            event = await self.client.async_get_event()
            rooms = await self.client.async_get_rooms()
            talks = await self.client.async_get_talks()
        except PretalxError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        locale = event.get("locale")
        parsed_rooms = {
            room["id"]: PretalxRoom(
                room_id=room["id"], name=_localized(room["name"], locale)
            )
            for room in rooms
        }
        sessions: dict[int, list[PretalxSession]] = {
            room_id: [] for room_id in parsed_rooms
        }

        for talk in talks:
            speakers = [speaker["name"] for speaker in talk.get("speakers", [])]
            description = _build_description(speakers, talk.get("abstract") or "")
            for slot in talk.get("slots", []):
                room = slot.get("room")
                if room is None or not slot.get("start") or not slot.get("end"):
                    continue
                room_id = room["id"]
                room_name = _localized(room["name"], locale)
                sessions.setdefault(room_id, [])
                if room_id not in parsed_rooms:
                    parsed_rooms[room_id] = PretalxRoom(room_id=room_id, name=room_name)
                sessions[room_id].append(
                    PretalxSession(
                        uid=str(slot["id"]),
                        title=talk["title"],
                        start=datetime.fromisoformat(slot["start"]),
                        end=datetime.fromisoformat(slot["end"]),
                        room_name=room_name,
                        description=description,
                    )
                )

        for room_sessions in sessions.values():
            room_sessions.sort(key=lambda session: session.start)

        return PretalxData(
            event_name=_localized(event["name"], locale),
            rooms=parsed_rooms,
            sessions=sessions,
        )
