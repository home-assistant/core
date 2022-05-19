"""Support for WLED updates."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .helpers import wled_exception_handler
from .models import WLEDEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED update based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WLEDUpdateEntity(coordinator)])


class WLEDUpdateEntity(WLEDEntity, UpdateEntity):
    """Defines a WLED update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )
    _attr_title = "WLED"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Firmware"
        self._attr_unique_id = coordinator.data.info.mac_address

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
            (beta := self.coordinator.data.info.version_latest_beta) is not None
            and (current := self.coordinator.data.info.version) is not None
            and (current.alpha or current.beta or current.release_candidate)
            and (
                (stable := self.coordinator.data.info.version_latest_stable) is None
                or (stable is not None and stable < beta)
            )
        ):
            return str(beta)

        if (stable := self.coordinator.data.info.version_latest_stable) is not None:
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
