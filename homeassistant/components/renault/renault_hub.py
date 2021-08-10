"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

from datetime import timedelta
import logging

from renault_api.gigya.exceptions import InvalidCredentialsException
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_KAMEREON_ACCOUNT_ID, DEFAULT_SCAN_INTERVAL
from .renault_vehicle import RenaultVehicleProxy

LOGGER = logging.getLogger(__name__)


class RenaultHub:
    """Handle account communication with Renault servers."""

    def __init__(self, hass: HomeAssistant, locale: str) -> None:
        """Initialise proxy."""
        LOGGER.debug("Creating RenaultHub")
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
        if vehicles.vehicleLinks:
            for vehicle_link in vehicles.vehicleLinks:
                if vehicle_link.vin and vehicle_link.vehicleDetails:
                    # Generate vehicle proxy
                    vehicle = RenaultVehicleProxy(
                        hass=self._hass,
                        vehicle=await self._account.get_api_vehicle(vehicle_link.vin),
                        details=vehicle_link.vehicleDetails,
                        scan_interval=scan_interval,
                    )
                    await vehicle.async_initialise()
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
