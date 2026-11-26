"""Provides the Fully Kiosk Browser DataUpdateCoordinator."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import re
from typing import Any, cast, override

import aiohttp
from awesomeversion import AwesomeVersion
import defusedxml.ElementTree as ET
from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_PORT, DOMAIN, LOGGER, UPDATE_INTERVAL

UPDATE_FEED_URL = "https://www.fully-kiosk.com/feed/media"
UPDATE_FEED_INTERVAL = timedelta(hours=12)
UPDATE_FEED_RETRY_INTERVAL = timedelta(minutes=15)

type FullyKioskConfigEntry = ConfigEntry[FullyKioskDataUpdateCoordinator]

APK_FILENAME_REGEX = re.compile(
    r"^(?P<app>[\w-]+)-v(?P<version>\d+(?:\.\d+)+)(?:-(?P<variant>[\w-]+))?\.apk$"
)

RELEASES_KEY: HassKey[FullyKioskReleasesDataUpdateCoordinator] = HassKey(
    f"{DOMAIN}_releases"
)


@dataclass(frozen=True)
class FullyKioskRelease:
    """Represents a Fully Kiosk release."""

    app: str
    version: str
    variant: str | None
    url: str
    description: str | None


@dataclass(frozen=True)
class FullyKioskReleaseInfo:
    """Release information for Fully Kiosk."""

    releases: list[FullyKioskRelease]

    def get_release(
        self, app: str, is_emm: bool, version: str | None = None
    ) -> FullyKioskRelease | None:
        """Get the requested or latest release of the app and edition."""
        variant = "emm" if is_emm else None
        if version is not None:
            version = version.removesuffix("-emm")
        return max(
            (
                release
                for release in self.releases
                if release.app == app
                and release.variant == variant
                and version in (None, release.version)
            ),
            key=lambda release: AwesomeVersion(release.version),
            default=None,
        )


class FullyKioskReleasesDataUpdateCoordinator(
    TimestampDataUpdateCoordinator[FullyKioskReleaseInfo]
):
    """Class to manage fetching Fully Kiosk APK releases from RSS feed."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the releases updater."""
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass,
            LOGGER,
            config_entry=None,
            name=f"{DOMAIN}_releases",
            update_interval=UPDATE_FEED_INTERVAL,
        )
        self._refresh_task: asyncio.Task[None] | None = None

    @callback
    def async_refresh_if_stale(self) -> None:
        """Refresh missing or stale releases, sharing an ongoing refresh."""
        if self._refresh_task and not self._refresh_task.done():
            return
        if (
            self.last_update_success
            and self.last_update_success_time
            and dt_util.utcnow() - self.last_update_success_time < UPDATE_FEED_INTERVAL
        ):
            return
        self._refresh_task = self.hass.async_create_background_task(
            self.async_refresh(), f"{DOMAIN} releases refresh"
        )

    @override
    async def _async_update_data(self) -> FullyKioskReleaseInfo:
        """Fetch APK releases from the RSS feed."""
        try:
            async with asyncio.timeout(15):
                response = await self.session.get(UPDATE_FEED_URL)
                response.raise_for_status()
                content = await response.read()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_feed_communication_error",
                retry_after=UPDATE_FEED_RETRY_INTERVAL.total_seconds(),
            ) from err

        try:
            root = ET.fromstring(content)
        except ET.ParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_feed_parse_error",
                retry_after=UPDATE_FEED_RETRY_INTERVAL.total_seconds(),
            ) from err

        releases: list[FullyKioskRelease] = []
        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")
            description = item.findtext("description")
            if not title or not link:
                continue
            if match := APK_FILENAME_REGEX.match(title.strip()):
                releases.append(
                    FullyKioskRelease(
                        app=match.group("app"),
                        version=match.group("version"),
                        variant=match.group("variant"),
                        url=link.strip(),
                        description=description.strip() if description else None,
                    )
                )

        return FullyKioskReleaseInfo(releases=releases)


@callback
def async_get_releases_coordinator(
    hass: HomeAssistant,
) -> FullyKioskReleasesDataUpdateCoordinator:
    """Get or create the shared Fully Kiosk releases coordinator."""
    if (coordinator := hass.data.get(RELEASES_KEY)) is None:
        coordinator = FullyKioskReleasesDataUpdateCoordinator(hass)
        hass.data[RELEASES_KEY] = coordinator
    coordinator.async_refresh_if_stale()
    return coordinator


class FullyKioskDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an object to hold Fully Kiosk Browser data."""

    config_entry: FullyKioskConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FullyKioskConfigEntry) -> None:
        """Initialize."""
        self.use_ssl = entry.data.get(CONF_SSL, False)
        self.fully = FullyKiosk(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            DEFAULT_PORT,
            entry.data[CONF_PASSWORD],
            use_ssl=self.use_ssl,
            verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.data[CONF_HOST],
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            async with asyncio.timeout(15):
                # Get device info and settings in parallel
                result = await asyncio.gather(
                    self.fully.getDeviceInfo(), self.fully.getSettings()
                )
                # Store settings under settings key in data
                result[0]["settings"] = result[1]
                return cast(dict[str, Any], result[0])
        except FullyKioskError as error:
            raise UpdateFailed(error) from error
        except (TimeoutError, aiohttp.ClientError) as error:
            # Also expected while the app restarts after an update
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="device_unreachable",
            ) from error
