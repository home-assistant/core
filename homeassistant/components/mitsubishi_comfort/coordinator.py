"""DataUpdateCoordinator for Mitsubishi Comfort devices."""

from collections.abc import Awaitable
import logging
from typing import override

from mitsubishi_comfort import CloudIndoorUnit, CommandResult, IndoorUnit, KumoStation
from mitsubishi_comfort.exceptions import AuthenticationError, MitsubishiComfortError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type MitsubishiComfortConfigEntry = ConfigEntry[dict[str, MitsubishiComfortCoordinator]]


class MitsubishiComfortCoordinator(
    DataUpdateCoordinator[IndoorUnit | CloudIndoorUnit | KumoStation]
):
    """Coordinator to poll a single Mitsubishi device."""

    config_entry: MitsubishiComfortConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MitsubishiComfortConfigEntry,
        device: IndoorUnit | CloudIndoorUnit | KumoStation,
        mac: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"mitsubishi_comfort_{device.serial}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.device = device
        self.mac = mac
        self.data = device

    @override
    async def _async_update_data(self) -> IndoorUnit | CloudIndoorUnit | KumoStation:
        """Poll the device and return it."""
        try:
            success = await self.device.update_status()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Mitsubishi cloud authentication failed"
            ) from err
        except Exception as err:
            # The user-facing UpdateFailed message is translated and omits the IP;
            # log it here so the failing address is visible in debug logs.
            _LOGGER.debug(
                "Error polling %s at %s: %s",
                self.device.name,
                self.device.address,
                err,
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        if not success:
            _LOGGER.debug(
                "%s at %s returned no data", self.device.name, self.device.address
            )
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
