"""Proxy to handle account communication with Renault servers via PyZE."""
import asyncio

from pyze.api import BasicCredentialStore, Gigya, Kamereon, Vehicle

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_GIGYA_APIKEY,
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_KAMEREON_APIKEY,
    CONF_LOCALE,
    LOGGER,
)
from .pyzevehicleproxy import PyzeVehicleProxy


class PyzeProxy:
    """Handle account communication with Renault servers via PyZE."""

    def __init__(self, hass, config_data):
        """Initialise proxy."""
        LOGGER.debug("Creating PyzeProxy")
        self._hass = hass
        self._config_data = config_data
        self._gigya = None
        self._kamereon = None
        self._vehicle_links = None
        self._vehicle_proxies = {}
        self._vehicles_lock = asyncio.Lock()
        self.entities = []

    async def setup(self, load_vehicles: bool):
        """Set up proxy."""
        credential_store = BasicCredentialStore()
        credential_store.store(
            "gigya-api-key", self._config_data.get(CONF_GIGYA_APIKEY), None
        )
        credential_store.store(
            "kamereon-api-key", self._config_data.get(CONF_KAMEREON_APIKEY), None
        )
        locale = self._config_data[CONF_LOCALE]

        self._gigya = Gigya(
            credentials=credential_store,
        )
        self._kamereon = Kamereon(
            gigya=self._gigya,
            credentials=credential_store,
            country=locale[-2:],
        )

        if not await self.attempt_login():
            return False
        self.set_kamereon_account_id(self._config_data[CONF_KAMEREON_ACCOUNT_ID])
        if load_vehicles:
            vehicles = await self._hass.async_add_executor_job(
                self._kamereon.get_vehicles
            )
            self._vehicle_links = vehicles["vehicleLinks"]
        return True

    async def attempt_login(self) -> bool:
        """Attempt login to Renault servers."""
        try:
            if await self._hass.async_add_executor_job(
                self._gigya.login,
                self._config_data[CONF_USERNAME],
                self._config_data[CONF_PASSWORD],
            ):
                return True
        except RuntimeError as ex:
            LOGGER.error("Login to Gigya failed: %s", ex)
        return False

    async def get_account_ids(self) -> list:
        """Get Kamereon account ids."""
        await self._hass.async_add_executor_job(self._gigya.account_info)

        accounts = []
        for account_details in await self._hass.async_add_executor_job(
            self._kamereon.get_accounts
        ):
            accounts.append(account_details["accountId"])
        return accounts

    def set_kamereon_account_id(self, accountid):
        """Set Kamereon account id."""
        self._kamereon.set_account_id(accountid)

    def get_vehicle_links(self):
        """Get list of vehicles."""
        return self._vehicle_links

    async def get_vehicle_from_vin(self, vin: str):
        """Get vehicle from VIN."""
        return self._vehicle_proxies[vin.upper()]

    async def get_vehicle_proxy(self, vehicle_link: dict):
        """Get a pyze proxy for the vehicle.

        Using lock to ensure vehicle proxies are only created once across all platforms.
        """
        vin: str = vehicle_link["vin"]
        vin = vin.upper()
        async with self._vehicles_lock:
            pyze_vehicle_proxy = self._vehicle_proxies.get(vin)
            if pyze_vehicle_proxy is None:
                pyze_vehicle_proxy = PyzeVehicleProxy(
                    self._hass,
                    vehicle_link,
                    Vehicle(vehicle_link["vin"], self._kamereon),
                )
                self._vehicle_proxies[vin] = pyze_vehicle_proxy
                await pyze_vehicle_proxy.async_initialise
        return self._vehicle_proxies[vin]
