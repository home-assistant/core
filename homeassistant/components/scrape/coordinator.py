"""Coordinator for the scrape component."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bs4 import BeautifulSoup

from homeassistant.components.rest import CONF_PAYLOAD_TEMPLATE, RestData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class ScrapeCoordinator(DataUpdateCoordinator[BeautifulSoup]):
    """Scrape Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        rest: RestData,
        rest_config: dict[str, Any],
        update_interval: timedelta,
    ) -> None:
        """Initialize Scrape coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Scrape Coordinator",
            update_interval=update_interval,
        )
        self._rest = rest
        self._rest_config = rest_config

    async def _async_update_data(self) -> BeautifulSoup:
        """Fetch data from Rest."""
        if CONF_RESOURCE_TEMPLATE in self._rest_config:
            self._rest.set_url(
                self._rest_config["resource_template"].async_render(parse_result=False)
            )
        if CONF_PAYLOAD_TEMPLATE in self._rest_config:
            self._rest.set_payload(
                self._rest_config["payload_template"].async_render(parse_result=False)
            )
        await self._rest.async_update()
        if (data := self._rest.data) is None:
            raise UpdateFailed("REST data is not available")
        soup = await self.hass.async_add_executor_job(BeautifulSoup, data, "lxml")
        _LOGGER.debug("Raw beautiful soup: %s", soup)
        return soup
