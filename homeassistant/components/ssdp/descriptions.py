"""The SSDP integration."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from defusedxml import ElementTree

from homeassistant.core import HomeAssistant, callback

from .util import etree_to_dict

_LOGGER = logging.getLogger(__name__)


class DescriptionManager:
    """Class to cache and manage fetching descriptions."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the manager."""
        self.hass = hass
        self._description_cache: dict[str, None | dict[str, str]] = {}

    async def fetch_description(
        self, xml_location: str | None
    ) -> None | dict[str, str]:
        """Fetch the location or get it from the cache."""
        if xml_location is None:
            return None
        if xml_location not in self._description_cache:
            try:
                self._description_cache[xml_location] = await self._fetch_description(
                    xml_location
                )
            except Exception:  # pylint: disable=broad-except
                # If it fails, cache the failure so we do not keep trying over and over
                self._description_cache[xml_location] = None
                _LOGGER.exception("Failed to fetch ssdp data from: %s", xml_location)

        return self._description_cache[xml_location]

    @callback
    def async_cached_description(self, xml_location: str) -> None | dict[str, str]:
        """Fetch the description from the cache."""
        return self._description_cache.get(xml_location)

    async def _fetch_description(self, xml_location: str) -> None | dict[str, str]:
        """Fetch an XML description."""
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        try:
            for _ in range(2):
                resp = await session.get(xml_location, timeout=5)
                # Samsung Smart TV sometimes returns an empty document the
                # first time. Retry once.
                if xml := await resp.text(errors="replace"):
                    break
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching %s: %s", xml_location, err)
            return None

        try:
            tree = ElementTree.fromstring(xml)
        except ElementTree.ParseError as err:
            _LOGGER.debug("Error parsing %s: %s", xml_location, err)
            return None

        root = etree_to_dict(tree).get("root") or {}
        return root.get("device") or {}
