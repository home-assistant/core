"""HACS Data client."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientSession, ClientTimeout
import voluptuous as vol

from .exceptions import HacsException, HacsNotModifiedException
from .utils.logger import LOGGER
from .utils.validate import (
    VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REPO_DATA,
)

CRITICAL_REMOVED_VALIDATORS = {
    "critical": VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA,
    "removed": VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA,
}


class HacsDataClient:
    """HACS Data client."""

    def __init__(self, session: ClientSession, client_name: str) -> None:
        """Initialize."""
        self._client_name = client_name
        self._etags = {}
        self._session = session

    async def _do_request(
        self,
        filename: str,
        section: str | None = None,
    ) -> dict[str, dict[str, Any]] | list[str]:
        """Do request."""
        endpoint = "/".join([v for v in [section, filename] if v is not None])
        try:
            response = await self._session.get(
                f"https://data-v2.hacs.xyz/{endpoint}",
                timeout=ClientTimeout(total=60),
                headers={
                    "User-Agent": self._client_name,
                    "If-None-Match": self._etags.get(endpoint, ""),
                },
            )
            if response.status == 304:
                raise HacsNotModifiedException() from None
            response.raise_for_status()
        except HacsNotModifiedException:
            raise
        except TimeoutError:
            raise HacsException("Timeout of 60s reached") from None
        except Exception as exception:
            raise HacsException(f"Error fetching data from HACS: {exception}") from exception

        self._etags[endpoint] = response.headers.get("etag")

        return await response.json()

    async def get_data(self, section: str | None, *, validate: bool) -> dict[str, dict[str, Any]]:
        """Get data."""
        data = await self._do_request(filename="data.json", section=section)
        if not validate:
            return data

        if section in VALIDATE_FETCHED_V2_REPO_DATA:
            validated = {}
            for key, repo_data in data.items():
                try:
                    validated[key] = VALIDATE_FETCHED_V2_REPO_DATA[section](repo_data)
                except vol.Invalid as exception:
                    LOGGER.info(
                        "Got invalid data for %s (%s)", repo_data.get("full_name", key), exception
                    )
                    continue

            return validated

        if not (validator := CRITICAL_REMOVED_VALIDATORS.get(section)):
            raise ValueError(f"Do not know how to validate {section}")

        validated = []
        for repo_data in data:
            try:
                validated.append(validator(repo_data))
            except vol.Invalid as exception:
                LOGGER.info("Got invalid data for %s (%s)", section, exception)
                continue

        return validated

    async def get_repositories(self, section: str) -> list[str]:
        """Get repositories."""
        return await self._do_request(filename="repositories.json", section=section)
