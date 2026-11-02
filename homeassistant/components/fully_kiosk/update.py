"""Fully Kiosk Browser update platform."""

import asyncio
from typing import Any, override

from aiohttp import ClientError
from fullykiosk.exceptions import FullyKioskError

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER, VERSION_HISTORY_URL
from .coordinator import (
    FullyKioskConfigEntry,
    FullyKioskDataUpdateCoordinator,
    FullyKioskRelease,
    FullyKioskReleasesDataUpdateCoordinator,
    async_get_releases_coordinator,
)
from .entity import FullyKioskEntity

PARALLEL_UPDATES = 1
POLL_INTERVAL = 2.0
INSTALL_TIMEOUT = 300.0


def _get_device_app(device_info: dict[str, Any]) -> str:
    """Return the app name corresponding to the device."""
    pkg = (
        device_info.get("appPackageName")
        or device_info.get("packageName")
        or device_info.get("foregroundApp")
        or ""
    )
    if pkg == "com.fullykiosk.singleapp":
        return "Fully-Single-App-Kiosk"
    if pkg == "com.fullykiosk.videokiosk":
        return "Fully-Video-Kiosk"
    return "Fully-Kiosk-Browser"


def _is_play_edition(device_info: dict[str, Any]) -> bool:
    """Return True if device is running Google Play edition."""
    version = str(device_info.get("appVersionName") or "").lower()
    installer = str(device_info.get("installerSource") or "").lower()
    return version.endswith("-play") or installer == "com.android.vending"


def _is_emm_edition(device_info: dict[str, Any]) -> bool:
    """Return True if device is running EMM edition."""
    version = str(device_info.get("appVersionName") or "").lower()
    pkg = str(
        device_info.get("packageName") or device_info.get("appPackageName") or ""
    ).lower()
    return version.endswith("-emm") or pkg == "com.fullykiosk.emm"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FullyKioskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser update entities."""
    coordinator: FullyKioskDataUpdateCoordinator = entry.runtime_data
    releases_coordinator = await async_get_releases_coordinator(hass)
    async_add_entities([FullyKioskUpdateEntity(coordinator, releases_coordinator)])


class FullyKioskUpdateEntity(FullyKioskEntity, UpdateEntity):
    """Fully Kiosk Browser update entity."""

    _attr_name = None
    _attr_release_url = VERSION_HISTORY_URL

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        releases_coordinator: FullyKioskReleasesDataUpdateCoordinator,
    ) -> None:
        """Initialize the Fully Kiosk Browser update entity."""
        super().__init__(coordinator)
        self.releases_coordinator = releases_coordinator
        self._attr_unique_id = coordinator.data["deviceID"]
        self._target_version: str | None = None
        self._installing: bool = False
        self._poll_task: asyncio.Task[None] | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.releases_coordinator.async_add_listener(self.async_write_ha_state)
        )
        self.async_on_remove(self._stop_poll_task)

    @callback
    def _stop_poll_task(self) -> None:
        """Cancel the install polling task if active."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None

    @callback
    def _start_poll_task(self, target_version: str, url: str) -> None:
        """Start background polling task for install progress."""
        self._stop_poll_task()
        self._poll_task = self.hass.async_create_background_task(
            self._async_poll_installation(target_version, url),
            name=f"fully_kiosk_install_{self.entity_id}",
        )

    async def _async_poll_installation(self, target_version: str, url: str) -> None:
        """Poll the device for installation progress and completion."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        has_started = False

        try:
            while loop.time() - start_time < INSTALL_TIMEOUT:
                await asyncio.sleep(POLL_INTERVAL)

                # Check if device updated and restarted with target version
                if self.installed_version == target_version:
                    break

                try:
                    state = await self.coordinator.fully.getInstallApkState()
                except ClientError, TimeoutError, FullyKioskError:
                    continue

                if not state or not isinstance(state, dict):
                    continue

                if (state_url := state.get("url")) and state_url != url:
                    continue

                status = state.get("status")

                if status in ("downloading", "installing"):
                    has_started = True

                if status in ("success", "idle") and (status != "idle" or has_started):
                    # Fully Kiosk process restarts upon successful APK installation.
                    # Retry coordinator refresh in case the web server is still booting up.
                    for _ in range(5):
                        await self.coordinator.async_refresh()
                        if self.coordinator.last_update_success:
                            break
                        await asyncio.sleep(1.0)
                    break

                if status == "failed":
                    error_msg = state.get("statustext") or "APK installation failed"
                    LOGGER.error(
                        "Installation of Fully Kiosk %s on %s failed: %s",
                        target_version,
                        self.coordinator.data.get("deviceName", self.entity_id),
                        error_msg,
                    )
                    break
            else:
                LOGGER.error(
                    "Installation of Fully Kiosk %s on %s timed out after %d seconds",
                    target_version,
                    self.coordinator.data.get("deviceName", self.entity_id),
                    int(INSTALL_TIMEOUT),
                )
        except FullyKioskError as err:
            LOGGER.error(
                "Installation of Fully Kiosk %s on %s failed: %s",
                target_version,
                self.coordinator.data.get("deviceName", self.entity_id),
                err.status,
            )
        except asyncio.CancelledError:
            pass
        finally:
            self._installing = False
            self._target_version = None
            self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self._installing
            and self._target_version
            and self.installed_version == self._target_version
        ):
            self._stop_poll_task()
            self._installing = False
            self._target_version = None
        super()._handle_coordinator_update()

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether an update is in progress."""
        return self._installing

    @property
    @override
    def available(self) -> bool:
        """Return if both the device and releases could be reached."""
        return (
            self._installing or super().available
        ) and self.releases_coordinator.last_update_success

    @override
    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        await self.releases_coordinator.async_request_refresh()

    @property
    @override
    def title(self) -> str | None:
        """Title of the software."""
        return _get_device_app(self.coordinator.data).replace("-", " ")

    @property
    @override
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.coordinator.data.get("appVersionName")

    @property
    @override
    def latest_version(self) -> str | None:
        """Return latest available version."""
        release = self._get_latest_release()
        if release is None:
            return None
        if _is_emm_edition(self.coordinator.data):
            return f"{release.version}-emm"
        return release.version

    @property
    @override
    def release_summary(self) -> str | None:
        """Return release summary."""
        release = self._get_latest_release()
        return release.description if release else None

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        if not _is_play_edition(self.coordinator.data):
            return (
                UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.SPECIFIC_VERSION
                | UpdateEntityFeature.PROGRESS
            )
        return UpdateEntityFeature(0)

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        clean_installed = installed_version.removesuffix("-play")
        return super().version_is_newer(latest_version, clean_installed)

    def _get_latest_release(self) -> FullyKioskRelease | None:
        """Get the latest release for the current device."""
        if not self.releases_coordinator.data:
            return None
        app = _get_device_app(self.coordinator.data)
        is_emm = _is_emm_edition(self.coordinator.data)
        return self.releases_coordinator.data.get_latest(app=app, is_emm=is_emm)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if _is_play_edition(self.coordinator.data):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="play_store_install_unsupported",
            )

        if not self.releases_coordinator.data:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_release_available",
            )

        app = _get_device_app(self.coordinator.data)
        is_emm = _is_emm_edition(self.coordinator.data)

        if version is not None:
            release = self.releases_coordinator.data.get_release(
                version=version, app=app, is_emm=is_emm
            )
            if release is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="version_not_found",
                    translation_placeholders={"version": version},
                )
        else:
            release = self._get_latest_release()
            if release is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="no_release_available",
                )

        target_version = f"{release.version}-emm" if is_emm else release.version
        force_install = version is not None and target_version == self.installed_version

        try:
            await self.coordinator.fully.loadApkFile(
                release.url, force_install=force_install
            )
        except FullyKioskError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="install_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self._installing = True
        self._target_version = target_version
        self.async_write_ha_state()

        self._start_poll_task(target_version, release.url)
