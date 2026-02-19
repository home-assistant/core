"""Coordinator for the School Holidays integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL_HOURS
from .utils import clean_string, create_calendar_event, ensure_date

_LOGGER = logging.getLogger(__name__)


class SchoolHolidaysCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to update the calendar at the specified interval."""

    def __init__(
        self, hass: HomeAssistant, country: str, region: str, config_entry: ConfigEntry
    ) -> None:
        """Initialize the data update coordinator."""
        self.country = country
        self.region = region
        super().__init__(
            hass,
            logger=_LOGGER,
            name="School Holidays",
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        country_methods = {
            "The Netherlands": self._get_school_holidays_nl,
        }

        country_method = country_methods.get(self.country)
        if country_method:
            _LOGGER.debug("Retrieving school holidays for country '%s'", self.country)
            return await country_method()

        _LOGGER.exception("Country '%s' is invalid", self.country)
        return []

    async def _get_school_holidays_nl(self) -> list[dict[str, Any]]:
        url = "https://opendata.rijksoverheid.nl/v1/sources/rijksoverheid/infotypes/schoolholidays?output=json"
        events: list[dict[str, Any]] = []

        _LOGGER.debug("Retrieving school holidays from '%s'", url)
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                if response.status != 200:
                    return []

                data = await response.json()
        except aiohttp.ClientError, TimeoutError:
            return []

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
                summary = vacation.get("type").strip()
                regions = vacation.get("regions", [])
                compulsory_dates = vacation.get("compulsorydates")
                use_notice = compulsory_dates is False or (
                    isinstance(compulsory_dates, str)
                    and compulsory_dates.lower() == "false"
                )

                for region_data in regions or []:
                    region = region_data.get("region").lower()
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
        except KeyError, TypeError, ValueError:
            return []

        return events
