"""Data update coordinator for Met Office Weather Warnings."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from logging import getLogger
import re
from typing import Final
from xml.etree import ElementTree as ET

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import BASE_URL, CONF_REGION, DOMAIN

_LOGGER = getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)
REFRESH_COOLDOWN: Final = 120

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
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the coordinator."""
        self._region = config_entry.data[CONF_REGION]
        self._url = BASE_URL.format(region=self._region)
        self._session = session
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {self._region}",
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REFRESH_COOLDOWN,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
            ),
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
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"url": self._url, "error": str(err)},
            ) from err

        try:
            root = ET.fromstring(text)  # noqa: S314
        except ET.ParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="parse_error",
                translation_placeholders={"url": self._url, "error": str(err)},
            ) from err

        channel = root.find("channel")
        if channel is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="missing_channel",
                translation_placeholders={"url": self._url},
            )

        pub_date: datetime | None = None
        pub_date_text = channel.findtext("pubDate")
        if pub_date_text:
            try:
                pub_date = datetime.strptime(
                    pub_date_text, "%a, %d %b %Y %H:%M:%S GMT"
                ).replace(tzinfo=UTC)
            except ValueError:
                _LOGGER.warning("Invalid pubDate format: %s", pub_date_text)

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


def _parse_warning_time(time_str: str, year: int | None) -> str:
    """Parse a time string like '0800 Wed 12 Mar' into ISO format."""
    try:
        dt = datetime.strptime(f"{year} {time_str}", "%Y %H%M %a %d %b")
    except ValueError:
        return time_str
    return dt.isoformat()
