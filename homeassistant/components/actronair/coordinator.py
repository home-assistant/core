"""ActronAir coordinators."""

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

from .const import AC_SYSTEMS, DOMAIN

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
            name="ActronAir AC Systems list",
            update_interval=ACCOUNT_SCAN_INTERVAL,
        )
        self.aa_api = aa_api
        self.acSystems = None

    async def _async_update_data(self) -> Any:
        """Fetch data from Account balance API endpoint."""
        try:
            async with asyncio.timeout(60):
                if DOMAIN not in self.hass.data:
                    self.hass.data[DOMAIN] = {}
                self.hass.data[DOMAIN][AC_SYSTEMS] = (
                    self.acSystems
                ) = await self.aa_api.async_getACSystems()
                return self.acSystems
        except AuthException as auth_err:
            raise ConfigEntryAuthFailed from auth_err
        except ApiException as api_err:
            raise UpdateFailed(
                f"Error communicating with AA API: {api_err}"
            ) from api_err

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

    ac_system_status_list: dict[str, SystemStatus] = {}
    aa_api: ActronAirApi = None

    def __init__(self, hass: HomeAssistant, aa_api: ActronAirApi) -> None:
        """Initialize ActronAirSystemStatusDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ActronAir AC System Status",
            update_interval=STATUS_SCAN_INTERVAL,
        )
        self.hass = hass
        self.aa_api = aa_api
        self.ac_system_status_list: dict[str, SystemStatus] = {}

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

            acSystems = self.hass.data[DOMAIN].get(AC_SYSTEMS, None)
            if acSystems is not None and len(acSystems) > 0:
                # self.ac_system_status_list: dict[str, SystemStatus] = {}
                for acSystem in acSystems:
                    async with asyncio.timeout(60):
                        ac_system_status = await self.aa_api.async_getACSystemStatus(
                            acSystem.serial
                        )
                    if ac_system_status is None or ac_system_status == {}:
                        raise UpdateFailed(
                            f"No status received for AC system {acSystem.serial}"
                        )
                    self.ac_system_status_list[acSystem.serial] = ac_system_status

        except AuthException as auth_err:
            raise ConfigEntryAuthFailed from auth_err
        except ApiException as api_err:
            raise UpdateFailed(
                f"Error communicating with AA API: {api_err}"
            ) from api_err
