"""Update platform for Flic Button integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .const import DOMAIN
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
    async_add_entities([FlicFirmwareUpdateEntity(coordinator)])


class FlicFirmwareUpdateEntity(FlicButtonEntity, UpdateEntity):
    """Firmware update entity for Flic devices."""

    _attr_auto_update = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}-firmware"
        self._auto_install_attempted = False

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._maybe_auto_install()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        self._maybe_auto_install()

    @callback
    def _maybe_auto_install(self) -> None:
        """Schedule auto-install if a firmware update is available."""
        if (
            not self._auto_install_attempted
            and not self.coordinator.firmware_update_in_progress
            and not self.coordinator.firmware_awaiting_reboot
            and self.installed_version is not None
            and self.latest_version is not None
            and self.version_is_newer(self.latest_version, self.installed_version)
        ):
            self._auto_install_attempted = True
            self.hass.async_create_background_task(
                self._async_auto_install(),
                name=f"{DOMAIN}_auto_install_{self.coordinator.client.address}",
            )

    async def _async_auto_install(self) -> None:
        """Auto-install firmware update."""
        try:
            _LOGGER.info(
                "Auto-installing firmware update for %s",
                self.coordinator.client.address,
            )
            await self.coordinator.async_install_firmware()
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Auto firmware install failed for %s, "
                "update can be retried from the update entity",
                self.coordinator.client.address,
            )

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
        # Handle the special +update suffix used when API offers a re-flash
        latest_clean = latest_version.split("+", maxsplit=1)[0]
        installed_clean = installed_version.split("+", maxsplit=1)[0]
        if latest_clean == installed_clean:
            return "+" in latest_version
        return super().version_is_newer(latest_clean, installed_clean)

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install a firmware update."""
        await self.coordinator.async_install_firmware()
