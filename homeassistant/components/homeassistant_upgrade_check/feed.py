"""Release feed for the Home Assistant Upgrade Check integration."""

import asyncio
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .release_notes import (
    INDEX_FORMAT,
    parse_release,
    parse_version,
    post_index,
    releases_between,
)

# The markdown source of the live site: the "current" branch of home-assistant.io.
# Until home-assistant.io publishes releases/index.json and releases/<version>.json,
# the index is built from this listing and each release parsed from its post.
POSTS_URL = (
    "https://api.github.com/repos/home-assistant/home-assistant.io"
    "/git/trees/current:source/_posts"
)
POST_URL = (
    "https://raw.githubusercontent.com/home-assistant/home-assistant.io"
    "/current/source/_posts/{name}"
)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
STORAGE_VERSION = 1


class ReleaseNotesUnavailable(HomeAssistantError):
    """The release posts could not be read."""


class ReleaseFeed:
    """Release notes for one running/target pair, fetched once and cached."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the feed."""
        self._hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, DOMAIN)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] | None = None

    async def async_get(self, running: str, target: str) -> list[dict[str, Any]]:
        """Return the release notes of the releases after running up to target."""
        key = f"{running}..{target}@{INDEX_FORMAT}"
        async with self._lock:
            if self._data is None:
                self._data = await self._store.async_load() or {}
            if self._data.get("key") != key:
                releases = await self._async_fetch(
                    parse_version(running), parse_version(target)
                )
                self._data = {"key": key, "releases": releases}
                await self._store.async_save(self._data)
            return self._data["releases"]

    async def _async_fetch(
        self, after: tuple[int, int], upto: tuple[int, int]
    ) -> list[dict[str, Any]]:
        """Download the release notes after one release up to another."""
        session = async_get_clientsession(self._hass)

        async def fetch(url: str) -> aiohttp.ClientResponse:
            response = await session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response

        async def fetch_release(release: dict[str, Any]) -> dict[str, Any]:
            post = await (await fetch(release["notes"])).text()
            return await self._hass.async_add_executor_job(parse_release, post, release)

        try:
            listing = await (await fetch(POSTS_URL)).json()
            index = post_index((entry["path"] for entry in listing["tree"]), POST_URL)
            return list(
                await asyncio.gather(
                    *map(fetch_release, releases_between(index, after, upto))
                )
            )
        except (aiohttp.ClientError, TimeoutError, KeyError) as err:
            raise ReleaseNotesUnavailable from err


DATA_FEED: HassKey[ReleaseFeed] = HassKey(DOMAIN)
