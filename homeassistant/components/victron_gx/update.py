"""Firmware updates for Victron GX devices."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any, override

from victron_mqtt import FirmwareUpdateState

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .hub import Hub, VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)

_FIRMWARE_UPDATE_URL = "https://www.victronenergy.com/blog/category/firmware-software/"
_INSTALL_POLL_INTERVAL = 1
_INSTALL_TIMEOUT = 2 * 60 * 60
_UPDATE_ERROR_REASONS = {
    FirmwareUpdateState.UPDATE_FILE_NOT_FOUND: "update_file_not_found",
    FirmwareUpdateState.ERROR_DURING_UPDATE: "error_during_update",
    FirmwareUpdateState.ERROR_DURING_CHECK: "error_during_check",
}


class FirmwareUpdateError(Exception):
    """Represent a firmware update failure shown by the GX device."""

    def __init__(self, reason: str) -> None:
        """Initialize a firmware update failure."""
        super().__init__(reason)
        self.reason = reason


async def _async_install_firmware_update(
    hub: Hub,
    available_version: str,
    update_progress: Callable[[int], None],
) -> None:
    """Install firmware and report progress until the target version is active."""
    initial_state, _ = hub.firmware_update_status
    stale_failure_state = (
        initial_state if initial_state in _UPDATE_ERROR_REASONS else None
    )
    hub.install_firmware_update()
    last_progress: int | None = None

    try:
        async with asyncio.timeout(_INSTALL_TIMEOUT):
            while True:
                state, progress = hub.firmware_update_status
                if stale_failure_state is not None:
                    if state is stale_failure_state:
                        await asyncio.sleep(_INSTALL_POLL_INTERVAL)
                        continue
                    stale_failure_state = None
                if state in _UPDATE_ERROR_REASONS:
                    raise FirmwareUpdateError(_UPDATE_ERROR_REASONS[state])

                normalized_progress = (
                    min(max(progress, 0), 100) if progress is not None else None
                )
                if state is FirmwareUpdateState.REBOOTING:
                    normalized_progress = 100
                if (
                    normalized_progress is not None
                    and normalized_progress != last_progress
                ):
                    update_progress(normalized_progress)
                    last_progress = normalized_progress

                installed_version, _ = hub.firmware_versions
                if installed_version == available_version:
                    if last_progress != 100:
                        update_progress(100)
                    return

                await asyncio.sleep(_INSTALL_POLL_INTERVAL)
    except TimeoutError as err:
        raise FirmwareUpdateError("update_timed_out") from err


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GX firmware update entity."""
    async_add_entities([VictronFirmwareUpdateEntity(config_entry)], True)


class VictronFirmwareUpdateEntity(UpdateEntity):
    """Represent the Venus OS firmware installed on a GX device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_release_url = _FIRMWARE_UPDATE_URL
    _attr_should_poll = True
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_translation_key = "venus_os_firmware"

    def __init__(self, entry: VictronGxConfigEntry) -> None:
        """Initialize the firmware update entity."""
        self._hub = entry.runtime_data
        self._installed_version, self._online_version = self._hub.firmware_versions
        self._attr_unique_id = f"{entry.unique_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_system_0")}
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed Venus OS version."""
        return self._installed_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available Venus OS version."""
        return self._online_version or self._installed_version

    @property
    @override
    def available(self) -> bool:
        """Return whether the installed firmware version is available."""
        return self.installed_version is not None

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return whether Victron offers a Venus OS firmware build."""
        return self._online_version is not None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest Venus OS firmware."""
        latest_version = self._online_version
        if latest_version is None:
            return

        self._attr_in_progress = True
        self.async_write_ha_state()

        @callback
        def _async_update_progress(progress: int) -> None:
            self._attr_update_percentage = progress
            self.async_write_ha_state()

        try:
            try:
                await _async_install_firmware_update(
                    self._hub, latest_version, _async_update_progress
                )
            except FirmwareUpdateError as err:
                _LOGGER.warning("GX firmware installation failed: %s", err.reason)
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh the entity from the latest in-memory MQTT values."""
        self._installed_version, self._online_version = self._hub.firmware_versions
