"""Home Assistant hardware firmware update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientSession
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .models import FirmwareManifest

_LOGGER = logging.getLogger(__name__)


FIRMWARE_REFRESH_INTERVAL = timedelta(hours=8)
NABU_CASA_FIRMWARE_RELEASES_URL = (
    "https://api.github.com/repos/NabuCasa/silabs-firmware-builder/releases/latest"
)


class FirmwareUpdateCoordinator(DataUpdateCoordinator[FirmwareManifest]):
    """Coordinator to manage firmware updates."""

    def __init__(self, hass: HomeAssistant, session: ClientSession) -> None:
        """Initialize the firmware update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="firmware update coordinator",
            update_interval=FIRMWARE_REFRESH_INTERVAL,
            always_update=False,
        )
        self.hass = hass
        self.session = session

        self._latest_release_url: str | None = None
        self._latest_manifest: FirmwareManifest | None = None

    async def _async_update_data(self) -> FirmwareManifest:
        # Fetch the latest release metadata
        async with self.session.get(
            NABU_CASA_FIRMWARE_RELEASES_URL,
            headers={"X-GitHub-Api-Version": "2022-11-28"},
            raise_for_status=True,
        ) as rsp:
            obj = await rsp.json()

        release_url = obj["html_url"]

        if release_url == self._latest_release_url:
            _LOGGER.debug("GitHub release URL has not changed")
            assert self._latest_manifest is not None
            return self._latest_manifest

        try:
            manifest_asset = next(
                a for a in obj["assets"] if a["name"] == "manifest.json"
            )
        except StopIteration as exc:
            raise UpdateFailed(
                "GitHub release assets haven't been uploaded yet"
            ) from exc

        # Within the metadata, download the `manifest.json` file
        async with self.session.get(
            manifest_asset["browser_download_url"], raise_for_status=True
        ) as rsp:
            manifest_obj = await rsp.json(content_type=None)

        manifest = FirmwareManifest.from_json(
            manifest_obj,
            html_url=URL(release_url),
            url=URL(manifest_asset["browser_download_url"]),
        )

        # Only set the release URL down here to make sure that we don't invalidate
        # future requests if an exception is raised halfway through this method
        self._latest_manifest = manifest
        self._latest_release_url = release_url

        return self._latest_manifest
