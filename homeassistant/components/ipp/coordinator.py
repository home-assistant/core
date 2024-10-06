"""Coordinator for The Internet Printing Protocol (IPP) integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TypedDict

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class IPPDataUpdateCoordinatorType(TypedDict):
    """Type for IPPDataUpdateCoordinator."""

    printer: IPPPrinter
    uptime: datetime


class IPPDataUpdateCoordinator(DataUpdateCoordinator[IPPDataUpdateCoordinatorType]):
    """Class to manage fetching IPP data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        base_path: str,
        tls: bool,
        verify_ssl: bool,
        device_id: str,
    ) -> None:
        """Initialize global IPP data updater."""
        self.device_id = device_id
        self.ipp = IPP(
            host=host,
            port=port,
            base_path=base_path,
            tls=tls,
            verify_ssl=verify_ssl,
            session=async_get_clientsession(hass, verify_ssl),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> IPPDataUpdateCoordinatorType:
        """Fetch data from IPP."""
        try:
            data = await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

        if self.data is None or self.data["printer"].info.uptime > data.info.uptime:
            uptime = utcnow() - timedelta(seconds=data.info.uptime)
        else:
            uptime = self.data["uptime"]

        return {"printer": data, "uptime": uptime}
