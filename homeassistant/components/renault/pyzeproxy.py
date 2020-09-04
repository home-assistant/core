"""Proxy to handle account communication with Renault servers via PyZE."""
import asyncio
import json

from pyze.api import BasicCredentialStore, Gigya, Kamereon, Vehicle

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE, LOGGER
from .pyzevehicleproxy import PyzeVehicleProxy

GIGYA_KEY = "gigya-key"
GIGYA_URL = "gigya-url"
KAMEREON_KEY = "kamereon-key"
KAMEREON_URL = "kamereon-url"


class PyzeProxy:
    """Handle account communication with Renault servers via PyZE."""

    def __init__(self, hass, config_data):
        """Initialise proxy."""
        LOGGER.debug("Creating PyzeProxy")
        self.hass = hass
        self._config_data = config_data
        self._gigya = None
        self._kamereon = None
        self._vehicle_links = None
        self._vehicle_proxies = {}
        self._vehicles_lock = asyncio.Lock()
        self.entities = []

    async def _async_init(self):
        """Preload the configuration."""
        locale = self._config_data[CONF_LOCALE]
        api_keys = await self.get_api_keys(locale)

        credential_store = BasicCredentialStore()
        self._gigya = Gigya(
            api_key=api_keys[GIGYA_KEY],
            root_url=api_keys[GIGYA_URL],
            credentials=credential_store,
        )
        self._kamereon = Kamereon(
            api_key=api_keys[KAMEREON_KEY],
            root_url=api_keys[KAMEREON_URL],
            credentials=credential_store,
            gigya=self._gigya,
            country=locale[-2:],
        )

    async def get_api_keys(self, locale) -> dict:
        """Preload the configuration.

        Hoping to remove this once PR request on underlying PyZE module is merged:
        https://github.com/jamesremuscat/pyze/pull/85
        """
        session = aiohttp_client.async_get_clientsession(self.hass)

        url = f"https://renault-wrd-prod-1-euw1-myrapp-one.s3-eu-west-1.amazonaws.com/configuration/android/config_{locale}.json"

        async with session.get(url) as response:
            responsetext = await response.text()
            if responsetext == "":
                responsetext = "{}"
            jsonresponse = json.loads(responsetext)

            return {
                GIGYA_KEY: jsonresponse["servers"]["gigyaProd"]["apikey"],
                GIGYA_URL: jsonresponse["servers"]["gigyaProd"]["target"],
                KAMEREON_KEY: jsonresponse["servers"]["wiredProd"]["apikey"],
                KAMEREON_URL: jsonresponse["servers"]["wiredProd"]["target"],
            }

    async def attempt_login(self) -> bool:
        """Attempt login to Renault servers."""
        await self._async_init()
        try:
            if await self.hass.async_add_executor_job(
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

    async def setup(self, load_vehicles: bool):
        """Check credentials."""
        if not await self.attempt_login():
            return False
        self.set_kamereon_account_id(self._config_data[CONF_KAMEREON_ACCOUNT_ID])
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
