"""Support for WLED updates."""

from typing import Any, cast, override

from wled import Releases, WLEDError, WLEDUpgradeError

from homeassistant.components.update import (
    DOMAIN as UPDATE_DOMAIN,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WLED_KEY
from .const import DOMAIN
from .coordinator import (
    WLEDConfigEntry,
    WLEDDataUpdateCoordinator,
    WLEDReleasesDataUpdateCoordinator,
)
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED update based on a config entry."""
    coordinator = entry.runtime_data

    # Without knowing where its firmware comes from, there is nothing to offer;
    # that includes removing an update entity it had before.
    if (repo := coordinator.data.info.repo) is None:
        entity_registry = er.async_get(hass)
        if entity_id := entity_registry.async_get_entity_id(
            UPDATE_DOMAIN, DOMAIN, coordinator.data.info.mac_address
        ):
            entity_registry.async_remove(entity_id)
        return

    releases = hass.data[WLED_KEY]
    if (releases_coordinator := releases.get(repo)) is None:
        releases_coordinator = releases[repo] = WLEDReleasesDataUpdateCoordinator(
            hass, repo
        )
        await releases_coordinator.async_request_refresh()

    async_add_entities([WLEDUpdateEntity(coordinator, releases_coordinator)])


class WLEDUpdateEntity(WLEDEntity, UpdateEntity):
    """Defines a WLED update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    _attr_title = "WLED"

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        releases_coordinator: WLEDReleasesDataUpdateCoordinator,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator=coordinator)
        self.releases_coordinator = releases_coordinator
        self._attr_unique_id = coordinator.data.info.mac_address
        # Whether a release has a firmware file for this device, by version.
        self._firmware_available: dict[str, bool] = {}
        self._firmware_checks: set[str] = set()

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the releases coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.releases_coordinator.async_add_listener(self._handle_releases_update)
        )
        self._async_check_firmware()

    @callback
    def _handle_releases_update(self) -> None:
        """Handle new release information."""
        self._async_check_firmware()
        self._handle_coordinator_update()

    @callback
    def _async_check_firmware(self) -> None:
        """Check whether this device has a firmware file for the newest version.

        Only once per version: a custom build, for example, has no file in any
        release, so that version can't be installed and isn't offered.
        """
        if (
            (version := self._newest_version()) is None
            or version == self.installed_version
            or version in self._firmware_available
            or version in self._firmware_checks
        ):
            return

        self._firmware_checks.add(version)
        self.hass.async_create_task(self._async_firmware_available(version))

    async def _async_firmware_available(self, version: str) -> None:
        """Ask the release whether it has a firmware file for this device."""
        try:
            available = await self.coordinator.wled.firmware_available(version=version)
        except WLEDError:
            # GitHub couldn't tell; keep offering it, and ask again with the
            # next release information. Installing tells for sure.
            return
        finally:
            self._firmware_checks.discard(version)

        self._firmware_available[version] = available
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.releases_coordinator.last_update_success

    @property
    @override
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        if (version := self.coordinator.data.info.version) is None:
            return None
        return str(version)

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if (version := self._newest_version()) is None:
            return None

        # A version without a firmware file for this device isn't an update.
        if self._firmware_available.get(version) is False:
            return self.installed_version

        return version

    def _newest_version(self) -> str | None:
        """Return the newest version released for this device's channel."""
        # Another device from the same repository may still be fetching them;
        # until then, the shared coordinator has no data.
        releases: Releases | None = self.releases_coordinator.data
        if releases is None:
            return None

        # If we already run a pre-release, we consider being on the beta channel.
        # Offer beta version upgrade, unless stable is newer
        if (
            (beta := releases.beta) is not None
            and (current := self.coordinator.data.info.version) is not None
            and (current.alpha or current.beta or current.release_candidate)
            and (
                (stable := releases.stable) is None
                or (stable is not None and stable < beta and current > stable)
            )
        ):
            return str(beta)

        if (stable := releases.stable) is not None:
            return str(stable)

        return None

    @property
    @override
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if (version := self.latest_version) is None:
            return None
        return (
            f"https://github.com/{self.releases_coordinator.repo}"
            f"/releases/tag/v{version}"
        )

    @wled_exception_handler
    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if version is None:
            # We cast here, as we know that the latest_version is a string.
            version = cast(str, self.latest_version)
        try:
            await self.coordinator.wled.upgrade(version=version)
        except WLEDUpgradeError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_upgrade_failed",
                translation_placeholders={"error": str(error)},
            ) from error
        await self.coordinator.async_refresh()

    @override
    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        await self.releases_coordinator.async_request_refresh()
