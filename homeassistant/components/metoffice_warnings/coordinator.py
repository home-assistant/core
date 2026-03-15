"""Data update coordinator for Met Office Weather Warnings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from logging import getLogger
import re

import aiohttp
from defusedxml import ElementTree as ET

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL, CONF_REGION, DOMAIN, SCAN_INTERVAL

_LOGGER = getLogger(__name__)

type MetOfficeWarningsConfigEntry = ConfigEntry[MetOfficeWarningsCoordinator]


@dataclass
class MetOfficeWarning:
    """Representation of a Met Office weather warning."""

    description: str
    link: str
    level: str | None
    warning_type: str | None
    start: str | None
    end: str | None


@dataclass
class MetOfficeWarningsData:
    """Data from the Met Office warnings RSS feed."""

    pub_date: datetime | None
    warnings: list[MetOfficeWarning]


class MetOfficeWarningsCoordinator(DataUpdateCoordinator[MetOfficeWarningsData]):
    """Coordinator to fetch Met Office weather warnings from RSS feed."""

    config_entry: MetOfficeWarningsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MetOfficeWarningsConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self._region = config_entry.data[CONF_REGION]
        self._url = BASE_URL.format(region=self._region)
        self._session = async_get_clientsession(hass)
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {self._region}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> MetOfficeWarningsData:
        """Fetch and parse the RSS feed."""
        try:
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error fetching feed from {self._url}: {err}") from err

        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise UpdateFailed(
                f"Error parsing feed XML from {self._url}: {err}"
            ) from err

        channel = root.find("channel")
        if channel is None:
            raise UpdateFailed(f"No channel element found in feed from {self._url}")

        pub_date: datetime | None = None
        pub_date_text = channel.findtext("pubDate")
        if pub_date_text:
            pub_date = parsedate_to_datetime(pub_date_text)

        warnings: list[MetOfficeWarning] = []
        for item in channel.findall("item"):
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")

            level = _parse_level(title)
            warning_type = _parse_warning_type(title)
            start, end = _parse_validity(description, pub_date)

            warnings.append(
                MetOfficeWarning(
                    description=description,
                    link=link,
                    level=level,
                    warning_type=warning_type,
                    start=start,
                    end=end,
                )
            )

        return MetOfficeWarningsData(pub_date=pub_date, warnings=warnings)


def _parse_level(title: str) -> str | None:
    """Extract warning level from title."""
    match = re.search(r"(Yellow|Amber|Red)", title, re.IGNORECASE)
    return match.group(1).capitalize() if match else None


def _parse_warning_type(title: str) -> str | None:
    """Extract warning type from title."""
    match = re.search(r"warning of (.+?) affecting", title, re.IGNORECASE)
    return match.group(1) if match else None


def _parse_validity(
    description: str, pub_date: datetime | None
) -> tuple[str | None, str | None]:
    """Extract start and end times from description."""
    match = re.search(r"valid from (.+?) to (.+?)$", description, re.IGNORECASE)
    if not match:
        return None, None

    start_str = match.group(1).strip()
    end_str = match.group(2).strip()

    year = pub_date.year if pub_date else None

    start = _parse_warning_time(start_str, year)
    end = _parse_warning_time(end_str, year)

    return start, end


def _parse_warning_time(time_str: str, year: int | None) -> str | None:
    """Parse a time string like '0800 Wed 12 Mar' into ISO format."""
    if year is None:
        return time_str

    match = re.match(r"(\d{4})\s+\w{3}\s+(\d{1,2})\s+(\w{3})", time_str.strip())
    if not match:
        return time_str

    time_part = match.group(1)
    day = match.group(2)
    month_str = match.group(3)

    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    month = months.get(month_str)
    if month is None:
        return time_str

    hour = int(time_part[:2])
    minute = int(time_part[2:])

    try:
        dt = datetime(year, month, int(day), hour, minute)
    except ValueError:
        return time_str

    return dt.isoformat()
