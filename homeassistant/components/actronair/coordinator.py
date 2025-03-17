"""Actron Air coordinators."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from actronair_api import (
    ACSystem,
    ActronAirApi,
    ApiException,
    AuthException,
    SystemStatus,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SELECTED_AC_SERIAL

_LOGGER = logging.getLogger(__name__)

ACCOUNT_SCAN_INTERVAL = timedelta(hours=1)
STATUS_SCAN_INTERVAL = timedelta(seconds=30)


class ActronAirACSystemsDataCoordinator(DataUpdateCoordinator[list[ACSystem]]):
    """ActronAir ACSystems Data object."""

    def __init__(self, hass: HomeAssistant, aa_api: ActronAirApi) -> None:
        """Initialize ActronAirACSystemsDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Air AC Systems list",
            update_interval=ACCOUNT_SCAN_INTERVAL,
        )
        self.aa_api = aa_api
        self.acSystems = None

    async def _async_update_data(self) -> Any:
        """Fetch data from Account balance API endpoint."""
        try:
            async with asyncio.timeout(60):
                self.acSystems = await self.aa_api.async_getACSystems()
                return self.acSystems
        except AuthException as auth_err:
            raise ConfigEntryAuthFailed from auth_err
        except ApiException as api_err:
            raise UpdateFailed(
                f"Error communicating with AA API: {api_err}"
            ) from api_err

    def get_acSystem_options(self) -> list[ACSystem] | None:
        """Get the acSystem options for selection."""
        return self.acSystems

    def get_unique_id(self) -> str:
        """Return a unique_id for this entity."""

        if not self.acSystems:
            return "no_serial_available"

        # Ensure all acSystems have valid serials
        serials = [
            acSystem.serial
            for acSystem in self.acSystems
            if acSystem and acSystem.serial
        ]

        if not serials:
            return "no_valid_serials"

        return "_".join(sorted(serials))


class ActronAirSystemStatusDataCoordinator(DataUpdateCoordinator[SystemStatus]):
    """ActronAir AC System Status Data object."""

    def __init__(self, hass: HomeAssistant, aa_api: ActronAirApi) -> None:
        """Initialize ActronAirSystemStatusDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Air AC System Status",
            update_interval=STATUS_SCAN_INTERVAL,
        )
        self.hass = hass
        self.aa_api = aa_api
        self.acSystemStatus: SystemStatus = {}

    async def async_added_to_hass(self):
        """Handle when the entity is added to Home Assistant."""
        # self._attr_available = True  # Mark entity as available
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _async_update_data(self) -> SystemStatus:
        """Fetch data from API endpoint."""
        try:
            if DOMAIN not in self.hass.data:
                self.hass.data[DOMAIN] = {}  # Initialize DOMAIN if missing

            selectedSerial = self.hass.data[DOMAIN].get(SELECTED_AC_SERIAL, None)
            if selectedSerial is not None and selectedSerial != {}:
                async with asyncio.timeout(60):
                    self.acSystemStatus = await self.aa_api.async_getACSystemStatus(
                        selectedSerial
                    )
                if self.acSystemStatus is None or self.acSystemStatus == {}:
                    raise UpdateFailed(
                        f"No status received for AC system {selectedSerial}"
                    )
                return self.acSystemStatus

        except AuthException as auth_err:
            raise ConfigEntryAuthFailed from auth_err
        except ApiException as api_err:
            raise UpdateFailed(
                f"Error communicating with AA API: {api_err}"
            ) from api_err
