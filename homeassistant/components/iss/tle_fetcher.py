"""TLE fetcher for ISS integration."""

from __future__ import annotations

import asyncio
import logging
import random

from aiohttp import ClientError, ClientSession

from .const import REQUEST_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class TleFetcher:
    """Fetches TLE data from multiple sources."""

    def __init__(self, session: ClientSession, user_agent: str) -> None:
        """Initialize the TLE fetcher.

        Args:
            session: aiohttp ClientSession for making requests
            user_agent: User-Agent string to identify ourselves in requests

        """
        self._session = session
        self._user_agent = user_agent

    async def fetch_tle_from_source(
        self, url: str, iss_norad_id: int
    ) -> tuple[str, str] | None:
        """Fetch TLE data from a single source URL.

        Args:
            url: URL to fetch TLE data from

        Returns:
            Tuple of (line1, line2) if successful, None otherwise

        """
        headers = {"User-Agent": self._user_agent}

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                text = await response.text()

            # Parse TLE data from response - look for ISS specifically (NORAD ID 25544)
            lines = [line.strip() for line in text.splitlines() if line.strip()]

            # Find ISS TLE lines by NORAD ID
            iss_id = str(iss_norad_id)
            for i, line in enumerate(lines):
                if line.startswith(f"1 {iss_id}U"):  # ISS line 1
                    if i + 1 < len(lines) and lines[i + 1].startswith(
                        f"2 {iss_id}"
                    ):  # ISS line 2
                        _LOGGER.debug("Successfully fetched ISS TLE from %s", url)
                        return (line, lines[i + 1])

            _LOGGER.warning(
                "No ISS TLE data (NORAD ID %s) found in response from %s",
                iss_norad_id,
                url,
            )

        except TimeoutError:
            _LOGGER.debug("Timeout fetching TLE from %s", url)
        except (ClientError, OSError) as err:
            _LOGGER.warning("Error fetching TLE from %s: %s", url, err)

        return None

    async def fetch_tle(
        self, sources: list[str], iss_norad_id: int
    ) -> tuple[str, str] | None:
        """Fetch TLE data from multiple sources.

        Tries sources in random order to spread load across servers.
        Stops at first successful fetch.

        Args:
            sources: List of TLE source URLs to try

        Returns:
            Tuple of (line1, line2) if successful, None if all sources failed

        """
        # Randomize source order to spread the load
        shuffled_sources = list(sources)
        random.shuffle(shuffled_sources)

        # Try each source until one succeeds
        for source_url in shuffled_sources:
            _LOGGER.debug("Trying TLE source: %s", source_url)
            tle_data = await self.fetch_tle_from_source(source_url, iss_norad_id)

            if tle_data:
                _LOGGER.debug("TLE lines:\n%s\n%s", tle_data[0], tle_data[1])
                return tle_data

        _LOGGER.warning("Failed to fetch TLE from all %d sources", len(sources))
        return None
