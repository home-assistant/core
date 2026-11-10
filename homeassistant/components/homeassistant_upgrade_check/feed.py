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
from .release_notes import INDEX_FORMAT, index_post, parse_version, release_posts

# The markdown source of the live site: the "current" branch of home-assistant.io.
# Both should become static release metadata published on home-assistant.io, like
# the alerts feed, so core neither lists the repository nor parses html posts.
# Path of least current resistance choosing blog posts as best source.
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
    """Release indexes for one running/target pair, fetched once and cached."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the feed."""
        self._hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, DOMAIN)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] | None = None

    async def async_get(self, running: str, target: str) -> list[dict[str, Any]]:
        """Return the indexes of the releases after running up to target."""
        key = f"{running}..{target}@{INDEX_FORMAT}"
        async with self._lock:
            if self._data is None:
                self._data = await self._store.async_load() or {}
            if self._data.get("key") != key:
                posts = await self._async_fetch_posts(
                    parse_version(running), parse_version(target)
                )
                indexes = await self._hass.async_add_executor_job(_index_posts, posts)
                self._data = {"key": key, "indexes": indexes}
                await self._store.async_save(self._data)
            return self._data["indexes"]

    async def _async_fetch_posts(
        self, after: tuple[int, int], upto: tuple[int, int]
    ) -> list[tuple[str, str, str]]:
        """Download the release posts after one release up to another."""
        session = async_get_clientsession(self._hass)

        async def fetch(url: str) -> aiohttp.ClientResponse:
            response = await session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response

        async def fetch_post(name: str) -> str:
            return await (await fetch(POST_URL.format(name=name))).text()

        try:
            listing = await (await fetch(POSTS_URL)).json()
            wanted = release_posts(
                (entry["path"] for entry in listing["tree"]), after, upto
            )
            texts = await asyncio.gather(*(fetch_post(name) for _, name, _ in wanted))
        except (aiohttp.ClientError, TimeoutError, KeyError) as err:
            raise ReleaseNotesUnavailable from err
        return [
            (version, url, text)
            for (version, _, url), text in zip(wanted, texts, strict=True)
        ]


def _index_posts(posts: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """Parse downloaded posts, given as (version, url, markdown)."""
    return [index_post(text, version, url) for version, url, text in posts]


DATA_FEED: HassKey[ReleaseFeed] = HassKey(DOMAIN)
