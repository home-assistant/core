"""Fully Kiosk Browser update platform."""

import asyncio
from typing import Any, cast, override

from aiohttp import ClientError
from fullykiosk.exceptions import FullyKioskError

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
    UpdateReleaseNotesMessage,
    UpdateReleaseNotesMessageSeverity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    FullyKioskConfigEntry,
    FullyKioskDataUpdateCoordinator,
    FullyKioskRelease,
    FullyKioskReleasesDataUpdateCoordinator,
    async_get_releases_coordinator,
)
from .entity import FullyKioskEntity

PARALLEL_UPDATES = 1

RELEASE_NOTES_MESSAGE_CONFIRM_INSTALL = UpdateReleaseNotesMessage(
    translation_domain=DOMAIN,
    translation_key="confirm_install",
    severity=UpdateReleaseNotesMessageSeverity.WARNING,
)

POLL_INTERVAL = 2
POLL_TIMEOUT = 10
INSTALL_TIMEOUT = 300

VERSION_HISTORY_URL = "https://www.fully-kiosk.com/docs/en/features/version-history"

# The current releases no longer support Android 5
MIN_ANDROID_SDK = 23

BROWSER_APP = "Fully-Kiosk-Browser"
EMM_PACKAGE = "com.fullykiosk.emm"
APP_BY_PACKAGE = {
    EMM_PACKAGE: BROWSER_APP,
    "com.fullykiosk.singleapp": "Fully-Single-App-Kiosk",
    "com.fullykiosk.videokiosk": "Fully-Video-Kiosk",
    "de.ozerov.fully": BROWSER_APP,
}


def _get_package(device_info: dict[str, Any]) -> str | None:
    """Return the package name of the app, not reported by all versions."""
    return device_info.get("packageName") or device_info.get("appPackageName")


def _get_app(device_info: dict[str, Any]) -> str | None:
    """Return the app in the release feed, or None if it is not supported."""
    if (package := _get_package(device_info)) is None:
        return BROWSER_APP
    return APP_BY_PACKAGE.get(package)


def _is_emm_edition(device_info: dict[str, Any]) -> bool:
    """Return True if the device is running the EMM edition."""
    return (
        device_info["appVersionName"].endswith("-emm")
        or _get_package(device_info) == EMM_PACKAGE
    )


def _is_play_edition(device_info: dict[str, Any]) -> bool:
    """Return True if the device is running the Google Play edition."""
    return (
        device_info["appVersionName"].endswith("-play")
        or device_info.get("installerSource") == "com.android.vending"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FullyKioskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser update entities."""
    coordinator = entry.runtime_data
    if (app := _get_app(coordinator.data)) is None or coordinator.data.get(
        "androidSdk", MIN_ANDROID_SDK
    ) < MIN_ANDROID_SDK:
        return
    async_add_entities(
        [FullyKioskUpdateEntity(coordinator, async_get_releases_coordinator(hass), app)]
    )


class FullyKioskUpdateEntity(FullyKioskEntity, UpdateEntity):
    """Fully Kiosk Browser update entity."""

    _attr_name = None
    _attr_release_url = VERSION_HISTORY_URL

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        releases_coordinator: FullyKioskReleasesDataUpdateCoordinator,
        app: str,
    ) -> None:
        """Initialize the Fully Kiosk Browser update entity."""
        super().__init__(coordinator)
        self.releases_coordinator = releases_coordinator
        self._app = app
        self._attr_title = app.replace("-", " ")
        self._attr_unique_id = coordinator.data["deviceID"]

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.releases_coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the releases are known and the device is not unreachable."""
        # The app restarts during the installation
        return (
            self.in_progress is True or super().available
        ) and self.releases_coordinator.data_or_none is not None

    @override
    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        await self.releases_coordinator.async_request_refresh()

    @property
    @override
    def installed_version(self) -> str:
        """Return installed version."""
        return cast(str, self.coordinator.data["appVersionName"])

    @property
    @override
    def latest_version(self) -> str | None:
        """Return latest available version."""
        if (release := self._get_release()) is None:
            return None
        return self._installed_name(release)

    @property
    @override
    def release_summary(self) -> str | None:
        """Return release summary."""
        return release.description if (release := self._get_release()) else None

    @property
    @override
    def release_notes_messages(self) -> tuple[UpdateReleaseNotesMessage, ...]:
        """Messages shown before the release notes."""
        # Android only installs silently for device owners or with root
        if self.coordinator.data.get("isDeviceOwner") or self.coordinator.data.get(
            "isRooted"
        ):
            return ()
        return (RELEASE_NOTES_MESSAGE_CONFIRM_INSTALL,)

    @override
    async def async_release_notes(self) -> str | None:
        """Return the release summary, shown with the messages."""
        return self.release_summary

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        if _is_play_edition(self.coordinator.data):
            return UpdateEntityFeature(0)
        return (
            UpdateEntityFeature.INSTALL
            | UpdateEntityFeature.SPECIFIC_VERSION
            | UpdateEntityFeature.PROGRESS
            | UpdateEntityFeature.RELEASE_NOTES
        )

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        return super().version_is_newer(
            latest_version, installed_version.removesuffix("-play")
        )

    def _get_release(self, version: str | None = None) -> FullyKioskRelease | None:
        """Get the requested or latest release for the device."""
        return self.releases_coordinator.data.get_release(
            self._app, _is_emm_edition(self.coordinator.data), version
        )

    def _installed_name(self, release: FullyKioskRelease) -> str:
        """Return the version the device reports once the release is installed."""
        return (
            f"{release.version}-{release.variant}"
            if release.variant
            else release.version
        )

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update and wait until it is running."""
        if (release := self._get_release(version)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="version_not_found",
                translation_placeholders={"version": str(version)},
            )

        self._attr_in_progress = True
        self.async_write_ha_state()

        reinstall = self._installed_name(release) == self.installed_version
        try:
            await self.coordinator.fully.loadApkFile(
                release.url, force_install=reinstall
            )
        except (ClientError, TimeoutError, FullyKioskError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="install_failed",
            ) from err

        await self._async_wait_installed(release, reinstall=reinstall)

    async def _async_wait_installed(
        self, release: FullyKioskRelease, *, reinstall: bool
    ) -> None:
        """Wait until the device runs the release."""
        target_version = self._installed_name(release)
        started = False
        # Not a timeout context, cancelling a refresh would mark the device unavailable
        deadline = self.hass.loop.time() + INSTALL_TIMEOUT

        while reinstall or self.installed_version != target_version:
            if self.hass.loop.time() > deadline:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="install_timed_out",
                )
            await asyncio.sleep(POLL_INTERVAL)

            try:
                async with asyncio.timeout(POLL_TIMEOUT):
                    state = await self.coordinator.fully.getInstallApkState()
            except ClientError, TimeoutError, FullyKioskError:
                # The app is restarting
                continue

            if state.get("url", release.url) != release.url:
                continue

            status = state.get("status")
            if status == "failed":
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="install_failed",
                )
            if status in ("downloading", "installing"):
                started = True
                continue

            started = started or status == "success"
            if not started:
                continue

            await self.coordinator.async_refresh()
            # The version does not tell when a reinstallation is done
            if reinstall and self.coordinator.last_update_success:
                return
