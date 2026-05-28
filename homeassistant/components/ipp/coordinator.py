"""Coordinator for The Internet Printing Protocol (IPP) integration."""

from dataclasses import dataclass
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

# Integer page-count attributes returned by Get-Printer-Attributes
PAGE_COUNT_INT_ATTRIBUTES = (
    "printer-impressions-completed",
    "printer-pages-completed",
    "printer-media-sheets-completed",
)

# Collection page-count attributes — dicts of monochrome/full-color sub-counters
PAGE_COUNT_COLLECTION_ATTRIBUTES = ("printer-impressions-completed-col",)

REQUESTED_PAGE_COUNT_ATTRIBUTES = (
    *PAGE_COUNT_INT_ATTRIBUTES,
    *PAGE_COUNT_COLLECTION_ATTRIBUTES,
)

_LOGGER = logging.getLogger(__name__)

type IPPConfigEntry = ConfigEntry[IPPDataUpdateCoordinator]


@dataclass
class IPPData:
    """Data fetched from an IPP printer."""

    printer: IPPPrinter
    page_counts: dict[str, int]


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPData]):
    """Class to manage fetching IPP data from single endpoint."""

    config_entry: IPPConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: IPPConfigEntry) -> None:
        """Initialize global IPP data updater."""
        self.device_id = config_entry.unique_id or config_entry.entry_id
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

    async def _async_update_data(self) -> IPPData:
        """Fetch data from IPP."""
        try:
            printer = await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

        # Page counts are fetched via a separate request for now. Once pyipp PR #715
        # (https://github.com/ctalkington/python-ipp/pull/715) is merged, page
        # counters will be included in printer.counters by default and this extra
        # request can be removed.
        previous_page_counts = self.data.page_counts if self.data else {}
        page_counts = await self._async_fetch_page_counts(previous_page_counts)

        return IPPData(printer=printer, page_counts=page_counts)

    async def _async_fetch_page_counts(
        self, previous_page_counts: dict[str, int]
    ) -> dict[str, int]:
        """Fetch page count attributes from the printer."""
        try:
            response = await self.ipp.execute(
                IppOperation.GET_PRINTER_ATTRIBUTES,
                {
                    "operation-attributes-tag": {
                        "requested-attributes": REQUESTED_PAGE_COUNT_ATTRIBUTES,
                    },
                },
            )
        except Exception:
            _LOGGER.debug(
                "Failed to fetch page count attributes from printer", exc_info=True
            )
            return previous_page_counts

        parsed: dict[str, Any] = next(iter(response.get("printers") or []), {})
        page_counts: dict[str, int] = {}

        for attr in PAGE_COUNT_INT_ATTRIBUTES:
            if (value := parsed.get(attr)) is not None:
                page_counts[attr] = value

        for attr in PAGE_COUNT_COLLECTION_ATTRIBUTES:
            if isinstance(collection := parsed.get(attr), dict):
                for sub_key, sub_value in collection.items():
                    if sub_value is not None:
                        page_counts[f"{attr}/{sub_key}"] = sub_value

        return page_counts
