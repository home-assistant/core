"""Provides a centralized hub for requesting data to the server."""

from datetime import datetime
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant

from .feed import Feed

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Hub for EmonCMS."""

    manufacturer = "EmonCMS"

    def __init__(self, hass: HomeAssistant, host: str, api_key: str) -> None:
        """Init hub."""
        self._host = host
        self._hass = hass
        self._name = host
        self._api_key = api_key
        self._id = (
            host.lower()
            .removeprefix("http://")
            .removeprefix("https://")
            .removesuffix("/")
            .replace(".", "_")
        )
        self.online = True

    @property
    def hub_id(self) -> str:
        """Returns the generated ID from the target server."""
        return self._id

    async def get_feeds(self) -> list[Feed]:
        """Request the server a list of all the feeds available."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._host}/feed/list.json",
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                result: list = await response.json()

                _LOGGER.info("Got %d feeds", len(result))

                feeds: list[Feed] = []
                for entry in result:
                    feeds.append(
                        Feed(
                            int(entry["id"]),
                            int(entry["userid"]),
                            entry["name"],
                            entry["tag"],
                            entry["public"] == "1",
                            entry["size"],
                            int(entry["engine"]),
                            entry["unit"],
                        )
                    )

                return feeds

    async def fetch_feed_value(self, feed: Feed) -> tuple[datetime | None, str]:
        """Fetch the current value of the given feed. Returns update time and raw value."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._host}/feed/timevalue.json?id={feed.id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                result: Any = await response.json()
                time: datetime | None = (
                    datetime.fromtimestamp(int(result["time"]))
                    if result["time"] is not None
                    else None
                )
                value: str = str(result["value"])
                return time, value

    async def test_connection(self) -> bool:
        """Test connectivity to target server."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._host}/feed/list.json",
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                await response.json()
                return response.status == 200
