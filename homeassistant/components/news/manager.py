"""NewsManager for the news integration."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientError
import async_timeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (
    ATTR_ACTIVE,
    ATTR_DESCRIPTION,
    ATTR_DISMISSED,
    ATTR_EVENTS,
    ATTR_SOURCE,
    ATTR_SOURCES,
    ATTR_TITLE,
    ATTR_URL,
    DISPATCHER_NEWS_EVENT,
    EVENT_DATA_SCHEMA,
    SOURCES_SCHEMA,
    STORAGE_KEY,
    STORAGE_VERSION,
    NewsSource,
)
from .source_alerts import source_update_alerts

_LOGGER: logging.Logger = logging.getLogger(__name__)


class NewsManager:
    """Class to manage news events from sources."""

    def __init__(self, hass) -> None:
        """Initialize the NewsManager class."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict = {}

    @property
    def events(self) -> dict:
        """Return active events."""
        return self._data[ATTR_ACTIVE]

    @property
    def sources(self) -> dict:
        """Return the sources."""
        return self._data[ATTR_SOURCES]

    def source_events(self, source: str) -> dict:
        """Return all active events for a spesific source."""
        return {
            event_key: event_data
            for (event_key, event_data) in self._data[ATTR_ACTIVE].items()
            if event_data[ATTR_SOURCE] == source
        }

    async def manage_sources(self, sources: SOURCES_SCHEMA):
        """Manage news sources."""
        old_sources = self._data[ATTR_SOURCES]
        self._data[ATTR_SOURCES] = sources

        await asyncio.gather(
            *[
                self._dismiss_source_events(source)
                for source in self._data[ATTR_SOURCES]
                if not self._data[ATTR_SOURCES][source] and old_sources[source]
            ]
        )
        await self.update_sources()
        await self._store.async_save(self._data)

    async def load(self):
        """Load data from store."""
        self._data = await self._store.async_load() or {
            ATTR_ACTIVE: {},
            ATTR_DISMISSED: [],
            ATTR_SOURCES: {NewsSource.ALERTS: True},
        }

    async def update_sources(self) -> None:
        """Update data from sources."""
        enabled_sources = []
        if self._data[ATTR_SOURCES][NewsSource.ALERTS]:
            enabled_sources.append(source_update_alerts(self.hass, self))

        await asyncio.gather(*enabled_sources)

    async def register_event(
        self, source: str, event_id: str, event_data: dict
    ) -> str | None:
        """Register a news event."""
        event_key = f"{source}.{slugify(event_id)}".lower()
        event_data = EVENT_DATA_SCHEMA(event_data)

        if (
            event_key in self._data[ATTR_DISMISSED]
            or event_key in self._data[ATTR_ACTIVE]
        ):
            return None

        event_data[ATTR_SOURCE] = source

        _LOGGER.debug("Registering new event %s", event_key)
        self._data[ATTR_ACTIVE][event_key] = {
            ATTR_SOURCE: source,
            ATTR_TITLE: event_data[ATTR_TITLE],
            ATTR_DESCRIPTION: event_data[ATTR_DESCRIPTION],
            ATTR_URL: event_data[ATTR_URL],
        }

        async_dispatcher_send(
            self.hass, DISPATCHER_NEWS_EVENT, {ATTR_EVENTS: self.events}
        )
        await self._store.async_save(self._data)

        return event_key

    async def dismiss_event(self, event_key: str):
        """Dismiss a news event."""
        if (
            event_key in self._data[ATTR_DISMISSED]
            or event_key not in self._data[ATTR_ACTIVE]
        ):
            return

        del self._data[ATTR_ACTIVE][event_key]
        self._data[ATTR_DISMISSED].append(event_key)

        async_dispatcher_send(
            self.hass, DISPATCHER_NEWS_EVENT, {ATTR_EVENTS: self.events}
        )
        await self._store.async_save(self._data)

    async def _dismiss_source_events(self, source: str | NewsSource):
        """Dismiss all events for a source."""
        await asyncio.gather(
            *[
                self.dismiss_event(event)
                for event in self._data[ATTR_ACTIVE]
                if self._data[ATTR_ACTIVE][event][ATTR_SOURCE] == source
            ]
        )

    async def get_external_source_data(
        self, url: str, source: NewsSource
    ) -> list | dict | None:
        """Get external source data."""
        data = None
        try:
            session = async_get_clientsession(self.hass)
            async with async_timeout.timeout(30):
                response = await session.get(url)
        except ClientError as err:
            _LOGGER.error(
                "Could not update source '%s' from '%s' - %s", source, url, err
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Request timed out while updating the source '%s' from '%s'",
                source,
                url,
            )
        else:
            data = await response.json()

        return data
