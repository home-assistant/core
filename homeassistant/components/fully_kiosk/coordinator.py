"""Provides the Fully Kiosk Browser DataUpdateCoordinator."""

import asyncio
from dataclasses import dataclass
import re
from typing import Any, cast, override

import aiohttp
from awesomeversion import AwesomeVersion
import defusedxml.ElementTree as ET
from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.hass_dict import HassKey

from .const import (
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
    UPDATE_FEED_INTERVAL,
    UPDATE_FEED_URL,
    UPDATE_INTERVAL,
)

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

    def get_latest(
        self, app: str = "Fully-Kiosk-Browser", is_emm: bool = False
    ) -> FullyKioskRelease | None:
        """Get the latest release for the specified app and edition."""
        target_variant = "emm" if is_emm else None
        matching = [
            r for r in self.releases if r.app == app and r.variant == target_variant
        ]
        if not matching:
            return None
        return max(matching, key=lambda r: AwesomeVersion(r.version))

    def get_release(
        self,
        version: str,
        app: str = "Fully-Kiosk-Browser",
        is_emm: bool = False,
    ) -> FullyKioskRelease | None:
        """Get a specific release for the specified app, edition and version."""
        target_variant = "emm" if is_emm else None
        clean_version = version.removesuffix("-emm")
        for r in self.releases:
            if (
                r.app == app
                and r.variant == target_variant
                and r.version == clean_version
            ):
                return r
        return None


class FullyKioskReleasesDataUpdateCoordinator(
    DataUpdateCoordinator[FullyKioskReleaseInfo]
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
                translation_placeholders={"error": str(err)},
            ) from err

        try:
            root = ET.fromstring(content)
        except ET.ParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_feed_parse_error",
                translation_placeholders={"error": str(err)},
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


async def async_get_releases_coordinator(
    hass: HomeAssistant,
) -> FullyKioskReleasesDataUpdateCoordinator:
    """Get or create the shared Fully Kiosk releases coordinator."""
    if (coordinator := hass.data.get(RELEASES_KEY)) is None:
        coordinator = FullyKioskReleasesDataUpdateCoordinator(hass)
        hass.data[RELEASES_KEY] = coordinator
        await coordinator.async_refresh()
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
        except (FullyKioskError, aiohttp.ClientError, TimeoutError) as error:
            raise UpdateFailed(error) from error
