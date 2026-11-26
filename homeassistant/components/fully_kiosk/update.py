"""Fully Kiosk Browser update platform."""

from typing import Any, cast, override

from aiohttp import ClientError
from fullykiosk.exceptions import FullyKioskError
from fullykiosk.releases import (
    EDITION_PLAY,
    Release,
    canInstallApkSilently,
    getApp,
    getEdition,
    getRelease,
    versionKey,
)

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
    FullyKioskReleasesDataUpdateCoordinator,
    async_get_releases_coordinator,
)
from .entity import FullyKioskEntity

PARALLEL_UPDATES = 1

VERSION_HISTORY_URL = "https://www.fully-kiosk.com/docs/en/features/version-history"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FullyKioskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser update entities."""
    coordinator = entry.runtime_data
    if (app := getApp(coordinator.data)) is None:
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
        return cast(str, release.versionName)

    @property
    @override
    def release_notes_messages(self) -> tuple[UpdateReleaseNotesMessage, ...]:
        """Explain how the latest release is installed."""
        if (release := self._get_release()) is None:
            return ()
        placeholders = {"version": release.versionName, "apk_url": release.url}
        if canInstallApkSilently(self.coordinator.data):
            return (
                UpdateReleaseNotesMessage(
                    translation_domain=DOMAIN,
                    translation_key="install_without_confirmation",
                    translation_placeholders=placeholders,
                ),
            )
        return (
            UpdateReleaseNotesMessage(
                translation_domain=DOMAIN,
                translation_key="install_with_confirmation",
                severity=UpdateReleaseNotesMessageSeverity.WARNING,
                translation_placeholders=placeholders,
            ),
        )

    @override
    async def async_release_notes(self) -> str | None:
        """Return no release notes, the feed only links the APK."""
        return None

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        if getEdition(self.coordinator.data) == EDITION_PLAY:
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
        return cast(bool, versionKey(latest_version) > versionKey(installed_version))

    def _get_release(self, version: str | None = None) -> Release | None:
        """Get the requested or latest release for the device."""
        return getRelease(
            self.releases_coordinator.data, self.coordinator.data, version
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
        if self.version_is_newer(self.installed_version, release.versionName):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="downgrade_not_supported",
                translation_placeholders={"version": release.versionName},
            )

        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await self.coordinator.fully.installRelease(release)
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="install_timed_out",
            ) from err
        except (ClientError, FullyKioskError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="install_failed",
            ) from err
        await self.coordinator.async_refresh()
