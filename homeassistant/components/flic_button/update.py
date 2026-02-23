"""Update platform for Flic Button integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .coordinator import FlicCoordinator
from .entity import FlicButtonEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button update entities."""
    coordinator = entry.runtime_data

    if coordinator.is_twist:
        async_add_entities([FlicTwistUpdateEntity(coordinator)])


class FlicTwistUpdateEntity(FlicButtonEntity, UpdateEntity):
    """Firmware update entity for Flic Twist."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}-firmware"

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Stay available while awaiting device reboot after firmware update
        so the UI shows progress instead of unavailable.
        """
        if self.coordinator.firmware_awaiting_reboot:
            return True
        return super().available

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        version = self.coordinator.firmware_version
        return str(version) if version is not None else None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        When a firmware download URL is available, the API has indicated
        a firmware is ready to install. If the reported version equals the
        installed version, append a '+update' suffix so HA recognises it
        as a distinct (installable) version.
        """
        latest = self.coordinator.latest_firmware_version
        if latest is not None:
            latest_str = str(latest)
            # If versions match but a download URL exists, the API is
            # offering a firmware (could be a re-flash or downgrade).
            # Suffix the version so HA treats it as different.
            if (
                latest_str == self.installed_version
                and self.coordinator.firmware_download_url
            ):
                return f"{latest_str}+update"
            return latest_str
        # If no check done yet, return installed to avoid false "update available"
        return self.installed_version

    @property
    def in_progress(self) -> bool:
        """Return if an update is in progress."""
        return self.coordinator.firmware_update_in_progress

    @property
    def update_percentage(self) -> int | None:
        """Return the update progress percentage."""
        return self.coordinator.firmware_update_percentage

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return if latest_version is newer than installed_version."""
        try:
            return True
        except (ValueError, TypeError):
            return False

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install a firmware update."""

        def _progress_callback(bytes_acked: int, total_bytes: int) -> None:
            """Update progress percentage."""
            if total_bytes > 0:
                self.coordinator.set_firmware_update_percentage(
                    int(bytes_acked * 100 / total_bytes)
                )
                self.async_write_ha_state()

        await self.coordinator.async_install_firmware(
            progress_callback=_progress_callback,
        )
