"""The QNAP QSW coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aioqsw.exceptions import QswError
from aioqsw.localapi import QnapQswApi
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, QSW_TIMEOUT_SEC

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class QswUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the QNAP QSW device."""

    def __init__(self, hass: HomeAssistant, qsw: QnapQswApi) -> None:
        """Initialize."""
        self.qsw = qsw

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with async_timeout.timeout(QSW_TIMEOUT_SEC):
            try:
                await self.qsw.update()
            except QswError as error:
                raise UpdateFailed(error) from error
            return self.qsw.data()
