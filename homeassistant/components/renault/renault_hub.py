"""Proxy to handle account communication with Renault servers."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from renault_api.gigya.exceptions import InvalidCredentialsException
from renault_api.kamereon.models import KamereonVehiclesLink
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_MODEL_ID,
    ATTR_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from . import RenaultConfigEntry

from time import time

from .const import (
    CONF_KAMEREON_ACCOUNT_ID,
    COOLING_UPDATES_SECONDS,
    MAX_CALLS_PER_HOURS,
)
from .renault_vehicle import COORDINATORS, RenaultVehicleProxy

LOGGER = logging.getLogger(__name__)


class RenaultHub:
    """Handle account communication with Renault servers."""

    def __init__(self, hass: HomeAssistant, locale: str) -> None:
        """Initialise proxy."""
        self._hass = hass
        self._client = RenaultClient(
            websession=async_get_clientsession(self._hass), locale=locale
        )
        self._account: RenaultAccount | None = None
        self._vehicles: dict[str, RenaultVehicleProxy] = {}

        self._got_throttled_at_time: float | None = None

    def set_throttled(self) -> None:
        """We got throttled, we need to adjust the rate limit."""
        if self._got_throttled_at_time is None:
            self._got_throttled_at_time = time()

    def is_throttled(self) -> bool:
        """Check if we are throttled."""
        if self._got_throttled_at_time is None:
            return False

        if time() - self._got_throttled_at_time > COOLING_UPDATES_SECONDS:
            self._got_throttled_at_time = None
            return False

        return True

    async def attempt_login(self, username: str, password: str) -> bool:
        """Attempt login to Renault servers."""
        try:
            await self._client.session.login(username, password)
        except InvalidCredentialsException as ex:
            LOGGER.error("Login to Renault failed: %s", ex.error_details)
        else:
            return True
        return False

    async def async_initialise(self, config_entry: RenaultConfigEntry) -> None:
        """Set up proxy."""
        account_id: str = config_entry.data[CONF_KAMEREON_ACCOUNT_ID]

        self._account = await self._client.get_api_account(account_id)
        vehicles = await self._account.get_vehicles()
        if vehicles.vehicleLinks:
            if any(
                vehicle_link.vehicleDetails is None
                for vehicle_link in vehicles.vehicleLinks
            ):
                raise ConfigEntryNotReady(
                    "Failed to retrieve vehicle details from Renault servers"
                )

            num_call_per_scan = len(COORDINATORS) * len(vehicles.vehicleLinks)
            scan_interval = timedelta(
                seconds=(3600 * num_call_per_scan) / MAX_CALLS_PER_HOURS
            )

            device_registry = dr.async_get(self._hass)
            await asyncio.gather(
                *(
                    self.async_initialise_vehicle(
                        vehicle_link,
                        self._account,
                        scan_interval,
                        config_entry,
                        device_registry,
                    )
                    for vehicle_link in vehicles.vehicleLinks
                )
            )

            # all vehicles have been initiated with the right number of active coordinators
            num_call_per_scan = 0
            for vehicle_link in vehicles.vehicleLinks:
                vehicle = self._vehicles[str(vehicle_link.vin)]
                num_call_per_scan += len(vehicle.coordinators)

            new_scan_interval = timedelta(
                seconds=(3600 * num_call_per_scan) / MAX_CALLS_PER_HOURS
            )
            if new_scan_interval != scan_interval:
                # we need to change the vehicles with the right scan interval
                for vehicle_link in vehicles.vehicleLinks:
                    vehicle = self._vehicles[str(vehicle_link.vin)]
                    vehicle.update_scan_interval(new_scan_interval)

    async def async_initialise_vehicle(
        self,
        vehicle_link: KamereonVehiclesLink,
        renault_account: RenaultAccount,
        scan_interval: timedelta,
        config_entry: RenaultConfigEntry,
        device_registry: dr.DeviceRegistry,
    ) -> None:
        """Set up proxy."""
        assert vehicle_link.vin is not None
        assert vehicle_link.vehicleDetails is not None
        # Generate vehicle proxy
        vehicle = RenaultVehicleProxy(
            hass=self._hass,
            config_entry=config_entry,
            hub=self,
            vehicle=await renault_account.get_api_vehicle(vehicle_link.vin),
            details=vehicle_link.vehicleDetails,
            scan_interval=scan_interval,
        )
        await vehicle.async_initialise()
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=vehicle.device_info[ATTR_IDENTIFIERS],
            manufacturer=vehicle.device_info[ATTR_MANUFACTURER],
            name=vehicle.device_info[ATTR_NAME],
            model=vehicle.device_info[ATTR_MODEL],
            model_id=vehicle.device_info[ATTR_MODEL_ID],
        )
        self._vehicles[vehicle_link.vin] = vehicle

    async def get_account_ids(self) -> list[str]:
        """Get Kamereon account ids."""
        accounts = []
        for account in await self._client.get_api_accounts():
            vehicles = await account.get_vehicles()

            # Only add the account if it has linked vehicles.
            if vehicles.vehicleLinks:
                accounts.append(account.account_id)
        return accounts

    @property
    def vehicles(self) -> dict[str, RenaultVehicleProxy]:
        """Get list of vehicles."""
        return self._vehicles
