"""Client for the catalog data."""

from typing import Any

from aiohttp import ClientSession, ClientTimeout
import probatio

from homeassistant.util.json import json_loads

from .const import DOMAIN
from .exceptions import MarketplaceError, NotModifiedError
from .utils.logger import LOGGER
from .utils.response import async_read_limited
from .utils.validate import (
    VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA,
    VALIDATE_FETCHED_V2_REPO_DATA,
)


class CatalogClient:
    """Fetch the catalog data the Marketplace is built from."""

    def __init__(self, session: ClientSession, client_name: str) -> None:
        """Initialize."""
        self._client_name = client_name
        self._etags: dict[str, str | None] = {}
        self._session = session

    async def async_get_category(self, category: str) -> dict[str, dict[str, Any]]:
        """Fetch the repositories of a category, by id, the valid ones only."""
        data, etag = await self._async_get_section(category)
        if not isinstance(data, dict):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="catalog_not_an_object",
                translation_placeholders={"section": category},
            )

        validator = VALIDATE_FETCHED_V2_REPO_DATA[category]
        repositories: dict[str, dict[str, Any]] = {}
        for key, repo_data in data.items():
            # The key becomes the repository id, in unique ids and in URLs
            if not (key.isascii() and key.isdecimal()):
                LOGGER.info("Got invalid data for %s (not a repository id)", key)
                continue
            if not isinstance(repo_data, dict):
                LOGGER.info("Got invalid data for %s (not an object)", key)
                continue
            try:
                repositories[key] = validator(repo_data)
            except probatio.Invalid as exception:
                LOGGER.info(
                    "Got invalid data for %s (%s)",
                    repo_data.get("full_name", key),
                    exception,
                )

        if data and not repositories:
            raise _nothing_valid(category)

        self._remember_etag(category, etag)
        return repositories

    async def async_get_removed(self) -> list[dict[str, Any]]:
        """Fetch the repositories removed from the catalog, the valid ones only."""
        return await self._async_get_list(
            "removed", VALIDATE_FETCHED_V2_REMOVED_REPO_SCHEMA
        )

    async def async_get_critical(self) -> list[dict[str, Any]]:
        """Fetch the repositories marked as critical, the valid ones only."""
        return await self._async_get_list(
            "critical", VALIDATE_FETCHED_V2_CRITICAL_REPO_SCHEMA
        )

    async def _async_get_list(
        self, section: str, validator: probatio.Schema
    ) -> list[dict[str, Any]]:
        """Fetch a section that is a list, the valid entries only."""
        data, etag = await self._async_get_section(section)
        if not isinstance(data, list):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="catalog_not_a_list",
                translation_placeholders={"section": section},
            )

        entries: list[dict[str, Any]] = []
        for entry in data:
            try:
                entries.append(validator(entry))
            except probatio.Invalid as exception:
                LOGGER.info("Got invalid data for %s (%s)", section, exception)

        # Read as empty, what is missing from it counts as taken out
        if data and not entries:
            raise _nothing_valid(section)

        self._remember_etag(section, etag)
        return entries

    def _remember_etag(self, section: str, etag: str | None) -> None:
        """Remember the ETag of a section that was usable.

        Not for a broken answer, or it would stick as not modified.
        """
        self._etags[f"{section}/data.json"] = etag

    async def _async_get_section(self, section: str) -> tuple[Any, str | None]:
        """Fetch a section of the catalog and its ETag, a 304 raises NotModifiedError."""
        endpoint = f"{section}/data.json"
        url = f"https://data-v2.hacs.xyz/{endpoint}"
        try:
            async with self._session.get(
                url,
                timeout=ClientTimeout(total=60),
                headers={
                    "User-Agent": self._client_name,
                    "If-None-Match": self._etags.get(endpoint) or "",
                },
            ) as response:
                if response.status == 304:
                    raise NotModifiedError from None  # noqa: TRY301 # re-raised untouched below
                response.raise_for_status()
                content = await async_read_limited(response, url)
                etag = response.headers.get("etag")
        except NotModifiedError:
            raise
        except TimeoutError:
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="catalog_timeout"
            ) from None
        except Exception as exception:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="catalog_unreachable",
                translation_placeholders={"error": str(exception)},
            ) from exception

        try:
            data = json_loads(content)
        except ValueError as exception:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="catalog_invalid_json",
                translation_placeholders={
                    "endpoint": endpoint,
                    "error": str(exception),
                },
            ) from exception

        return data, etag


def _nothing_valid(section: str) -> MarketplaceError:
    """Return the error for a section with entries, of which none are valid."""
    return MarketplaceError(
        translation_domain=DOMAIN,
        translation_key="catalog_nothing_valid",
        translation_placeholders={"section": section},
    )
