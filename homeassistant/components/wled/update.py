"""Support for WLED updates."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WLED_KEY, WLEDConfigEntry
from .coordinator import WLEDDataUpdateCoordinator, WLEDReleasesDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED update based on a config entry."""
    async_add_entities([WLEDUpdateEntity(entry.runtime_data, hass.data[WLED_KEY])])


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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the releases coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.releases_coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.releases_coordinator.last_update_success

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        if (version := self.coordinator.data.info.version) is None:
            return None
        return str(version)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        # If we already run a pre-release, we consider being on the beta channel.
        # Offer beta version upgrade, unless stable is newer
        if (
            (beta := self.releases_coordinator.data.beta) is not None
            and (current := self.coordinator.data.info.version) is not None
            and (current.alpha or current.beta or current.release_candidate)
            and (
                (stable := self.releases_coordinator.data.stable) is None
                or (stable is not None and stable < beta and current > stable)
            )
        ):
            return str(beta)

        if (stable := self.releases_coordinator.data.stable) is not None:
            return str(stable)

        return None

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if (version := self.latest_version) is None:
            return None
        return f"https://github.com/Aircoookie/WLED/releases/tag/v{version}"

    @wled_exception_handler
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if version is None:
            # We cast here, as we know that the latest_version is a string.
            version = cast(str, self.latest_version)
        await self.coordinator.wled.upgrade(version=version)
        await self.coordinator.async_refresh()
