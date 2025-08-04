"""Data update coordinator for Green Planet Energy."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GreenPlanetEnergyUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from Green Planet Energy API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.session = async_get_clientsession(hass)
        self.api_url = "https://mein.green-planet-energy.de/p2"

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self._fetch_electricity_prices()
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning("Error fetching data from Green Planet Energy API: %s", err)
            # Return empty data instead of raising an error
            # This prevents the integration from failing completely
            return {}

    async def _fetch_electricity_prices(self) -> dict[str, Any]:
        """Fetch electricity prices from Green Planet Energy API."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        payload = {
            "jsonrpc": "2.0",
            "method": "getVerbrauchspreisUndWindsignal",
            "params": {
                "von": today.strftime("%Y-%m-%d"),
                "bis": tomorrow.strftime("%Y-%m-%d"),
                "aggregatsZeitraum": "",
                "aggregatsTyp": "",
                "source": "Portal",
            },
            "id": 564,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://mein.green-planet-energy.de/dynamischer-tarif/strompreise",
        }

        try:
            async with asyncio.timeout(30):
                async with self.session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(
                            f"API request failed with status {response.status}"
                        )

                    data = await response.json(content_type=None)
                    return self._process_response(data)
        except TimeoutError as err:
            raise UpdateFailed("Timeout while communicating with API") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _process_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Process the API response and extract hourly prices."""
        processed_data: dict[str, Any] = {}

        if "result" not in response_data:
            _LOGGER.warning("No result data in API response")
            return processed_data

        result = response_data["result"]

        # Check for API errors
        if result.get("errorCode", 0) != 0:
            error_text = result.get("errorText", "Unknown API error")
            _LOGGER.error(
                "API returned error: %s (code: %s)", error_text, result.get("errorCode")
            )
            return processed_data

        # Get the time and price arrays
        datum_array = result.get("datum", [])
        wert_array = result.get("wert", [])

        if not datum_array or not wert_array or len(datum_array) != len(wert_array):
            _LOGGER.warning("Invalid or missing price data in API response")
            return processed_data

        # Process all data points from the API response
        for i, timestamp_str in enumerate(datum_array):
            try:
                # Parse timestamp string like "04.08.25, 09:00 Uhr"
                # Extract the hour from the timestamp
                if " Uhr" not in timestamp_str:
                    continue

                # Extract hour part (e.g., "09:00" from "04.08.25, 09:00 Uhr")
                time_part = timestamp_str.split(", ")[1].replace(" Uhr", "")
                hour_str = time_part.split(":")[0]
                hour = int(hour_str)

                # Extract date part (e.g., "04.08.25" from "04.08.25, 09:00 Uhr")
                date_part = timestamp_str.split(", ")[0]

                # Get today and tomorrow dates in the same format
                today = date.today()
                tomorrow = today + timedelta(days=1)
                today_str = today.strftime("%d.%m.%y")
                tomorrow_str = tomorrow.strftime("%d.%m.%y")

                # Determine if this is today's or tomorrow's data
                if date_part == today_str:
                    # Today's price
                    hour_key = f"gpe_price_{hour:02d}"
                elif date_part == tomorrow_str:
                    # Tomorrow's price
                    hour_key = f"gpe_price_{hour:02d}_tomorrow"
                else:
                    # Unknown date, skip
                    continue

                # Convert price string to float (handle German decimal comma)
                price_str = wert_array[i]
                price_value = float(price_str.replace(",", "."))
                processed_data[hour_key] = price_value

            except (ValueError, IndexError) as err:
                _LOGGER.debug("Error parsing price data at index %s: %s", i, err)
                continue

        _LOGGER.debug("Processed electricity prices: %s", processed_data)
        return processed_data
