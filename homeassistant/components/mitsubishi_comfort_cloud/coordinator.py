"""DataUpdateCoordinator for Mitsubishi Comfort Cloud devices."""

from collections.abc import Awaitable
import logging
from typing import override

from mitsubishi_comfort import CloudIndoorUnit, CommandResult
from mitsubishi_comfort.exceptions import AuthenticationError, MitsubishiComfortError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type MitsubishiComfortCloudConfigEntry = ConfigEntry[
    dict[str, MitsubishiComfortCloudCoordinator]
]


class MitsubishiComfortCloudCoordinator(DataUpdateCoordinator[CloudIndoorUnit]):
    """Coordinator to poll a single Mitsubishi device."""

    config_entry: MitsubishiComfortCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MitsubishiComfortCloudConfigEntry,
        device: CloudIndoorUnit,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{device.serial}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.device = device
        self.data = device

    @override
    async def _async_update_data(self) -> CloudIndoorUnit:
        """Poll the device and return it."""
        try:
            success = await self.device.update_status()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except MitsubishiComfortError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        if not success:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"device_name": self.device.name},
            )
        return self.device

    async def async_command(self, command: Awaitable[CommandResult]) -> CommandResult:
        """Translate cloud command failures and request reauthentication."""
        try:
            return await command
        except AuthenticationError:
            self.config_entry.async_start_reauth(self.hass)
        except MitsubishiComfortError as err:
            _LOGGER.debug("Command failed for %s: %s", self.device.name, err)
        return CommandResult(success=False)
