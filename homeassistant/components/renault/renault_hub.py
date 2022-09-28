"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from renault_api.gigya.exceptions import InvalidCredentialsException
from renault_api.kamereon.models import KamereonVehiclesLink
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_KAMEREON_ACCOUNT_ID, DEFAULT_SCAN_INTERVAL
from .renault_vehicle import RenaultVehicleProxy

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

    async def attempt_login(self, username: str, password: str) -> bool:
        """Attempt login to Renault servers."""
        try:
            await self._client.session.login(username, password)
        except InvalidCredentialsException as ex:
            LOGGER.error("Login to Renault failed: %s", ex.error_details)
        else:
            return True
        return False

    async def async_initialise(self, config_entry: ConfigEntry) -> None:
        """Set up proxy."""
        account_id: str = config_entry.data[CONF_KAMEREON_ACCOUNT_ID]
        scan_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

        self._account = await self._client.get_api_account(account_id)
        vehicles = await self._account.get_vehicles()
        device_registry = dr.async_get(self._hass)
        if vehicles.vehicleLinks:
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

    async def async_initialise_vehicle(
        self,
        vehicle_link: KamereonVehiclesLink,
        renault_account: RenaultAccount,
        scan_interval: timedelta,
        config_entry: ConfigEntry,
        device_registry: dr.DeviceRegistry,
    ) -> None:
        """Set up proxy."""
        assert vehicle_link.vin is not None
        assert vehicle_link.vehicleDetails is not None
        # Generate vehicle proxy
        vehicle = RenaultVehicleProxy(
            hass=self._hass,
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
            sw_version=vehicle.device_info[ATTR_SW_VERSION],
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
