"""Coordinator for The Internet Printing Protocol (IPP) integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyipp import IPP, IPPError, Printer as IPPPrinter
from pyipp.enums import IppOperation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BASE_PATH, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

PAGE_COUNT_ATTRIBUTES = [
    "printer-impressions-completed",
    "printer-pages-completed",
    "printer-media-sheets-completed",
    "printer-impressions-completed-col",
]

_LOGGER = logging.getLogger(__name__)

type IPPConfigEntry = ConfigEntry[IPPDataUpdateCoordinator]


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPPrinter]):
    """Class to manage fetching IPP data from single endpoint."""

    config_entry: IPPConfigEntry
    page_counts: dict[str, int]

    def __init__(self, hass: HomeAssistant, config_entry: IPPConfigEntry) -> None:
        """Initialize global IPP data updater."""
        self.device_id = config_entry.unique_id or config_entry.entry_id
        self.page_counts = {}
        self.ipp = IPP(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            base_path=config_entry.data[CONF_BASE_PATH],
            tls=config_entry.data[CONF_SSL],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
            session=async_get_clientsession(hass, config_entry.data[CONF_VERIFY_SSL]),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            printer = await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

        self.page_counts = await self._async_fetch_page_counts()

        return printer

    async def _async_fetch_page_counts(self) -> dict[str, int]:
        """Fetch page count attributes from the printer."""
        page_counts: dict[str, int] = {}

        try:
            response = await self.ipp.execute(
                IppOperation.GET_PRINTER_ATTRIBUTES,
                {
                    "operation-attributes-tag": {
                        "requested-attributes": PAGE_COUNT_ATTRIBUTES,
                    },
                },
            )
        except IPPError:
            return page_counts

        parsed: dict[str, Any] = next(
            iter(response.get("printers") or []), {}
        )
        for attr in PAGE_COUNT_ATTRIBUTES:
            if attr not in parsed:
                continue
            value = parsed[attr]
            if isinstance(value, int):
                page_counts[attr] = value
            elif isinstance(value, dict):
                # Handle collection attributes like
                # printer-impressions-completed-col
                # which contain sub-keys like "monochrome" and "full-color"
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, int):
                        page_counts[f"{attr}/{sub_key}"] = sub_value

        return page_counts
