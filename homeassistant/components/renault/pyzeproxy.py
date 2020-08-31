"""Proxy to handle account communication with Renault servers via PyZE."""
import asyncio

from pyze.api import BasicCredentialStore, Gigya, Kamereon, Vehicle

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_KAMEREON_ACCOUNT_ID,
    GIGYA_KEY,
    GIGYA_URL,
    KAMEREON_KEY,
    KAMEREON_URL,
    LOGGER,
)
from .pyzevehicleproxy import PyzeVehicleProxy


class PyzeProxy:
    """Handle account communication with Renault servers via PyZE."""

    def __init__(self, hass):
        """Initialise proxy."""
        LOGGER.debug("Creating PyzeProxy")
        self.hass = hass
        self._preload_config = None
        self._credential_store = BasicCredentialStore()
        self._gigya = None
        self._kamereon = None
        self._vehicle_links = None
        self._vehicle_proxies = {}
        self._vehicles_lock = asyncio.Lock()
        self.entities = []

    async def ensure_config_preloaded(self):
        """Preload the configuration.

        Will be removed once PR request on underlying PyZE module is merged.
        https://github.com/jamesremuscat/pyze/pull/85
        """
        if self._preload_config is not None:
            return

        self._gigya = Gigya(
            api_key=GIGYA_KEY,
            root_url=GIGYA_URL,
            credentials=self._credential_store,
        )
        self._kamereon = Kamereon(
            api_key=KAMEREON_KEY,
            root_url=KAMEREON_URL,
            credentials=self._credential_store,
            gigya=self._gigya,
        )

    async def attempt_login(self, username, password) -> bool:
        """Attempt login to Renault servers."""
        await self.ensure_config_preloaded()
        try:
            if await self.hass.async_add_executor_job(
                self._gigya.login, username, password
            ):
                return True
        except RuntimeError as ex:
            LOGGER.error("Login to Gigya failed: %s", ex)
        return False

    async def get_account_ids(self) -> list:
        """Get Kamereon account ids."""
        await self.hass.async_add_executor_job(self._gigya.account_info)

        accounts = []
        for account_details in await self.hass.async_add_executor_job(
            self._kamereon.get_accounts
        ):
            accounts.append(account_details["accountId"])
        return accounts

    def set_kamereon_account_id(self, accountid):
        """Set Kamereon account id."""
        self._kamereon.set_account_id(accountid)

    async def setup(self, config_entry, load_vehicles: bool):
        """Check credentials."""
        await self.ensure_config_preloaded()
        if not await self.attempt_login(
            config_entry[CONF_USERNAME], config_entry[CONF_PASSWORD]
        ):
            return False
        self.set_kamereon_account_id(config_entry[CONF_KAMEREON_ACCOUNT_ID])
        if load_vehicles:
            vehicles = await self.hass.async_add_executor_job(
                self._kamereon.get_vehicles
            )
            self._vehicle_links = vehicles["vehicleLinks"]
        return True

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
                    self.hass,
                    vehicle_link,
                    Vehicle(vehicle_link["vin"], self._kamereon),
                )
                self._vehicle_proxies[vin] = pyze_vehicle_proxy
                await pyze_vehicle_proxy.async_initialise
        return self._vehicle_proxies[vin]
