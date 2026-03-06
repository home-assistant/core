"""Data update coordinators for Reolink."""

from __future__ import annotations

import asyncio
import logging

from reolink_aio.exceptions import (
    CredentialsInvalidError,
    LoginPrivacyModeError,
    ReolinkError,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)

NUM_CRED_ERRORS = 3


class ReolinkDeviceCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Reolink device state updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: ReolinkHost,
        *,
        update_timeout: float,
        min_timeout: float,
    ) -> None:
        """Initialize the device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"reolink.{host.api.nvr_name}",
        )
        self.host = host
        self._update_timeout = update_timeout
        self._min_timeout = min_timeout
        self._last_known_firmware: dict[int | None, str | None] = {}
        self.firmware_coordinator: ReolinkFirmwareCoordinator | None = None

    async def _async_update_data(self) -> None:
        """Update the host state cache and renew the ONVIF-subscription."""
        async with asyncio.timeout(self._update_timeout):
            try:
                await self.host.update_states()
            except CredentialsInvalidError as err:
                self.host.credential_errors += 1
                if self.host.credential_errors >= NUM_CRED_ERRORS:
                    await self.host.stop()
                    raise ConfigEntryAuthFailed(err) from err
                raise UpdateFailed(str(err)) from err
            except LoginPrivacyModeError:
                pass  # HTTP API is shutdown when privacy mode is active
            except ReolinkError as err:
                self.host.credential_errors = 0
                raise UpdateFailed(str(err)) from err

        self.host.credential_errors = 0

        # Check for firmware version changes (external update detection)
        firmware_changed = False
        for ch in (*self.host.api.channels, None):
            new_version = self.host.api.camera_sw_version(ch)
            old_version = self._last_known_firmware.get(ch)
            if (
                old_version is not None
                and new_version is not None
                and new_version != old_version
            ):
                firmware_changed = True
            self._last_known_firmware[ch] = new_version

        # Notify firmware coordinator if firmware changed externally
        if firmware_changed and self.firmware_coordinator is not None:
            self.firmware_coordinator.async_set_updated_data(None)

        async with asyncio.timeout(self._min_timeout):
            await self.host.renew()

        if (
            self.host.api.new_devices
            and self.config_entry.state == ConfigEntryState.LOADED
        ):
            # Their are new cameras/chimes connected, reload to add them.
            _LOGGER.debug(
                "Reloading Reolink %s to add new device (capabilities)",
                self.host.api.nvr_name,
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )


class ReolinkFirmwareCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Reolink firmware update checks."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: ReolinkHost,
        *,
        min_timeout: float,
    ) -> None:
        """Initialize the firmware coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"reolink.{host.api.nvr_name}.firmware",
            update_interval=None,
        )
        self.host = host
        self._min_timeout = min_timeout

    async def _async_update_data(self) -> None:
        """Check for firmware updates."""
        async with asyncio.timeout(self._min_timeout):
            try:
                await self.host.api.check_new_firmware(self.host.firmware_ch_list)
            except ReolinkError as err:
                if self.host.starting:
                    _LOGGER.debug(
                        "Error checking Reolink firmware update at startup "
                        "from %s, possibly internet access is blocked",
                        self.host.api.nvr_name,
                    )
                    return

                raise UpdateFailed(
                    f"Error checking Reolink firmware update from {self.host.api.nvr_name}, "
                    "if the camera is blocked from accessing the internet, "
                    "disable the update entity"
                ) from err
            finally:
                self.host.starting = False
