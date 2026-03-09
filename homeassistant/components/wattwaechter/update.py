"""Firmware update platform for the WattWächter Plus integration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from aio_wattwaechter import WattwaechterAuthenticationError, WattwaechterConnectionError
from aio_wattwaechter.models import OtaData

from . import WattwaechterConfigEntry
from .const import DOMAIN, OTA_CHECK_INTERVAL
from .coordinator import WattwaechterCoordinator
from .entity import WattwaechterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WattWächter firmware update entity."""
    coordinator = entry.runtime_data
    async_add_entities([WattwaechterUpdateEntity(coordinator)])


class WattwaechterUpdateEntity(WattwaechterEntity, UpdateEntity):
    """Firmware update entity for WattWächter Plus."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    _attr_should_poll = True
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: WattwaechterCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_firmware_update"
        self._ota_data: OtaData | None = None
        self._last_check: float = 0

    async def async_added_to_hass(self) -> None:
        """Fetch OTA data when entity is added."""
        await super().async_added_to_hass()
        await self.async_update()

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return self.coordinator.fw_version or None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        if self._ota_data and self._ota_data.update_available:
            return self._ota_data.version
        return self.installed_version

    @property
    def release_summary(self) -> str | None:
        """Return release notes."""
        if not self._ota_data or not self._ota_data.update_available:
            return None
        # Try German first, fall back to English
        return self._ota_data.release_note_de or self._ota_data.release_note_en

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a firmware update."""
        try:
            await self.coordinator.client.ota_start()
        except WattwaechterAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_auth",
            ) from err
        except WattwaechterConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self._set_progress(5)

        try:
            if await self._wait_for_reboot():
                _LOGGER.info("WattWächter firmware update completed, refreshing data")
                self._set_progress(95)
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.warning(
                    "WattWächter device did not come back online after firmware update"
                )
        finally:
            self._attr_in_progress = False
            self.async_write_ha_state()

    def _set_progress(self, percent: int) -> None:
        """Update progress and push state to HA."""
        self._attr_in_progress = percent
        self.async_write_ha_state()

    async def _wait_for_reboot(self) -> bool:
        """Wait for device to reboot after OTA and come back online."""
        old_version = self.coordinator.fw_version
        device_went_offline = False

        # Phase 1: Device downloading firmware (5-50%)
        await asyncio.sleep(5)
        for i in range(24):  # poll every 5s, up to ~2 minutes
            try:
                result = await self.coordinator.client.alive()
                if device_went_offline:
                    _LOGGER.debug("Device back online after reboot")
                    self._set_progress(90)
                    return True
                new_version = result.version
                if new_version and new_version != old_version:
                    _LOGGER.debug("Firmware version changed: %s -> %s", old_version, new_version)
                    self._set_progress(90)
                    return True
                # Still online = downloading/flashing firmware
                self._set_progress(min(10 + i * 2, 45))
            except WattwaechterConnectionError:
                device_went_offline = True
                self._set_progress(50)
                _LOGGER.debug("Device offline, firmware update in progress")
            await asyncio.sleep(5)

        # Phase 2: If still not detected, final alive check
        try:
            await self.coordinator.client.alive()
            self._set_progress(90)
            return True
        except WattwaechterConnectionError:
            return False

    async def async_update(self) -> None:
        """Check for firmware updates periodically."""
        now = time.monotonic()
        if self._last_check > 0 and now - self._last_check < OTA_CHECK_INTERVAL:
            return

        self._last_check = now
        try:
            result = await self.coordinator.client.ota_check()
            self._ota_data = result.data
        except (WattwaechterConnectionError, WattwaechterAuthenticationError) as err:
            _LOGGER.debug("OTA check failed: %s", err)
