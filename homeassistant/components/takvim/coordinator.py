"""Coordinator for the Takvim prayer times integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Coordinator for retrieving Takvim prayer times."""

    def __init__(self, hass, district_id):
        """Initialize the coordinator."""
        self.district_id = district_id

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )

    async def _async_update_data(self):
        """Fetch prayer time data from the API."""
        url = f"{API_URL}?districtId={self.district_id}&lang=1"
        _LOGGER.debug("URL: %s", url)

        try:
            async with (
                asyncio.timeout(10),
                aiohttp.ClientSession() as session,
                session.get(url) as resp,
            ):
                data = await resp.json()

            _LOGGER.debug("JSON: %s", data)

            # Logik bleibt unverändert
            result = {
                "sabah": self._make_timestamp(
                    data.get("vakitler")[1].get("sabah")[0].get("tarih")
                ),
                "ogle": self._make_timestamp(
                    data.get("vakitler")[1].get("ogle")[0].get("tarih")
                ),
                "ikindi": self._make_timestamp(
                    data.get("vakitler")[1].get("ikindi")[0].get("tarih")
                ),
                "aksam": self._make_timestamp(
                    data.get("vakitler")[1].get("aksam")[0].get("tarih")
                ),
                "yatsi": self._make_timestamp(
                    data.get("vakitler")[1].get("yatsi")[0].get("tarih")
                ),
            }

            _LOGGER.debug("result: %s", result)

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching prayer times: {err}") from err

        else:
            return result

    def _make_timestamp(self, time_string: str) -> datetime:
        """Convert API ISO timestamp to Europe/Berlin timezone."""
        clean = time_string.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.astimezone(ZoneInfo("Europe/Berlin"))
