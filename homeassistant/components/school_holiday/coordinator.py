"""Coordinator for the School Holiday integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COUNTRY_NAMES, DOMAIN, LOGGER, SCAN_INTERVAL
from .utils import clean_string, create_calendar_event, ensure_date


class SchoolHolidayCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to update the calendar at the specified interval."""

    def __init__(
        self, hass: HomeAssistant, country: str, region: str, config_entry: ConfigEntry
    ) -> None:
        """Initialize the data update coordinator."""
        self.country = country
        self.region = region

        # Get the full country name for API calls.
        self.country_name = COUNTRY_NAMES.get(country, country)
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        country_methods = {
            "nl": self._get_school_holidays_nl,
        }

        country_method = country_methods.get(self.country)
        if country_method:
            LOGGER.debug("Retrieving school holidays for %s", self.country_name)
            return await country_method()

        LOGGER.error("Country '%s' is invalid", self.country)
        return []

    async def _get_school_holidays_nl(self) -> list[dict[str, Any]]:
        """Retrieve school holidays for The Netherlands."""
        url = "https://opendata.rijksoverheid.nl/v1/sources/rijksoverheid/infotypes/schoolholidays?output=json"
        events: list[dict[str, Any]] = []
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Failed to retrieve school holidays: HTTP {response.status}"
                    )

                data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Failed to retrieve school holidays: {err}") from err

        try:
            all_contents = []
            item_notices = {}

            for item in data:
                contents = item.get("content", [])
                if contents:
                    all_contents.extend(contents)
                    for content in contents:
                        item_notices[id(content)] = item.get("notice")

            all_vacations = []
            for content in all_contents:
                vacations = content.get("vacations", [])
                if vacations:
                    all_vacations.extend(
                        [(vacation, content) for vacation in vacations]
                    )

            school_holidays = []
            for vacation, content in all_vacations:
                vacation_type = vacation.get("type")
                if not isinstance(vacation_type, str):
                    LOGGER.debug(
                        "Skipping vacation with invalid type: %s", vacation_type
                    )
                    continue

                summary = vacation_type.strip()
                if not summary:
                    LOGGER.debug("Skipping vacation with empty type")
                    continue
                regions = vacation.get("regions", [])
                compulsory_dates = vacation.get("compulsorydates")
                use_notice = compulsory_dates is False or (
                    isinstance(compulsory_dates, str)
                    and compulsory_dates.lower() == "false"
                )

                for region_data in regions or []:
                    if not isinstance(region_data, dict):
                        LOGGER.debug(
                            "Skipping vacation with invalid region data: %s",
                            region_data,
                        )
                        continue

                    region_value = region_data.get("region")
                    if not isinstance(region_value, str):
                        LOGGER.debug(
                            "Skipping vacation with invalid region: %s", region_value
                        )
                        continue

                    region = region_value.lower()
                    if region not in (self.region.lower(), "heel nederland"):
                        continue

                    notice = item_notices.get(id(content)) if use_notice else None

                    school_holidays.append((summary, region_data, notice))

            for summary, region_data, notice in school_holidays:
                start_date = region_data.get("startdate")
                end_date = region_data.get("enddate")
                if not start_date or not end_date:
                    continue

                start = ensure_date(start_date)
                # Add 1 day to end date to make it inclusive.
                end = ensure_date(end_date) + timedelta(days=1)
                description = clean_string(notice)

                create_calendar_event(
                    events,
                    summary,
                    start,
                    end,
                    description,
                )
        except (KeyError, TypeError, ValueError) as err:
            raise UpdateFailed(f"Failed to parse school holidays data: {err}") from err

        return events
