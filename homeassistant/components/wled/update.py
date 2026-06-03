"""Support for WLED updates."""

from typing import Any, cast

from wled import Releases

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WLED_KEY
from .coordinator import (
    WLEDConfigEntry,
    WLEDDataUpdateCoordinator,
    WLEDReleasesDataUpdateCoordinator,
    normalize_repo,
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
    async_add_entities([WLEDUpdateEntity(entry.runtime_data, hass.data[WLED_KEY])])


class WLEDUpdateEntity(WLEDEntity, UpdateEntity):
    """Defines a WLED update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    _attr_name = "Firmware"
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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the releases coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.releases_coordinator.async_add_listener(
                self._handle_releases_coordinator_update
            )
        )
        await self.releases_coordinator.async_set_repo(
            self.coordinator.config_entry.entry_id, self._repo
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the device coordinator."""
        self.hass.async_create_task(
            self.releases_coordinator.async_set_repo(
                self.coordinator.config_entry.entry_id, self._repo
            )
        )
        super()._handle_coordinator_update()

    @callback
    def _handle_releases_coordinator_update(self) -> None:
        """Handle updated data from the releases coordinator."""
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """When removed from hass."""
        self.releases_coordinator.async_unset_repo(
            self.coordinator.config_entry.entry_id
        )
        await super().async_will_remove_from_hass()

    @property
    def _repo(self) -> str:
        """Return the repo to fetch releases for."""
        return normalize_repo(getattr(self.coordinator.data.info, "repo", None))

    @property
    def _release_info(self) -> Releases | None:
        """Return the release info for the current repo."""
        if (releases_by_repo := self.releases_coordinator.data) is None:
            return None
        return releases_by_repo.get(self._repo)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._release_info is not None

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        if (version := self.coordinator.data.info.version) is None:
            return None
        return str(version)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if (releases := self._release_info) is None:
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
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if (version := self.latest_version) is None:
            return None
        return f"https://github.com/{self._repo}/releases/tag/v{version}"

    @wled_exception_handler
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if version is None:
            # We cast here, as we know that the latest_version is a string.
            version = cast(str, self.latest_version)
        await self.coordinator.wled.upgrade(version=version, repo=self._repo)
        await self.coordinator.async_refresh()

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        await self.releases_coordinator.async_request_refresh()
