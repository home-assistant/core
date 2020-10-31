"""Proxy to handle account communication with Renault servers via PyZE."""
import asyncio
import logging
from typing import Dict

import aiohttp
from pyze.api import BasicCredentialStore, Gigya, Kamereon, Vehicle

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_GIGYA_APIKEY,
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_KAMEREON_APIKEY,
    CONF_LOCALE,
)
from .pyze_vehicle_proxy import PyZEVehicleProxy

LOGGER = logging.getLogger(__name__)

# Awaiting PR on parent package
# https://github.com/jamesremuscat/pyze/pull/89
AVAILABLE_LOCALES = [
    "bg_BG",
    "cs_CZ",
    "da_DK",
    "de_DE",
    "de_AT",
    "de_CH",
    "en_GB",
    "en_IE",
    "es_ES",
    "es_MX",
    "fi_FI",
    "fr_FR",
    "fr_BE",
    "fr_CH",
    "fr_LU",
    "hr_HR",
    "hu_HU",
    "it_IT",
    "it_CH",
    "nl_NL",
    "nl_BE",
    "no_NO",
    "pl_PL",
    "pt_PT",
    "ro_RO",
    "ru_RU",
    "sk_SK",
    "sl_SI",
    "sv_SE",
]


# Awaiting PR on parent package
# https://github.com/jamesremuscat/pyze/pull/85
async def get_api_keys_from_myrenault(
    session: aiohttp.ClientSession, locale: str
) -> Dict:
    """Handle loading of Renault localised API keys."""
    url = f"https://renault-wrd-prod-1-euw1-myrapp-one.s3-eu-west-1.amazonaws.com/configuration/android/config_{locale}.json"
    async with session.get(url) as response:
        response.raise_for_status()
        response_body = await response.json()

        LOGGER.debug("Received api keys from myrenault response: % s", response_body)

        servers = response_body["servers"]
        return {
            "gigya-api-key": servers["gigyaProd"]["apikey"],
            "gigya-api-url": servers["gigyaProd"]["target"],
            "kamereon-api-key": servers["wiredProd"]["apikey"],
            "kamereon-api-url": servers["wiredProd"]["target"],
        }


class PyZEProxy:
    """Handle account communication with Renault servers via PyZE."""

    def __init__(self, hass):
        """Initialise proxy."""
        self._hass = hass
        self._gigya = None
        self._kamereon = None
        self._vehicle_links = None
        self._vehicle_proxies = {}
        self._vehicles_lock = asyncio.Lock()
        self.entities = []

    def set_api_keys(self, config_data):
        """Set up gigya."""
        credential_store = BasicCredentialStore()
        credential_store.store(
            "gigya-api-key", config_data.get(CONF_GIGYA_APIKEY), None
        )
        credential_store.store(
            "kamereon-api-key", config_data.get(CONF_KAMEREON_APIKEY), None
        )

        self._gigya = Gigya(
            credentials=credential_store,
        )
        self._kamereon = Kamereon(
            gigya=self._gigya,
            credentials=credential_store,
            country=config_data.get(CONF_LOCALE)[-2:],
        )

    async def attempt_login(self, config_data) -> bool:
        """Attempt login to Renault servers."""
        if self._gigya is None:
            raise RuntimeError("Please ensure Gigya is initialised.")
        try:
            if await self._hass.async_add_executor_job(
                self._gigya.login,
                config_data[CONF_USERNAME],
                config_data[CONF_PASSWORD],
            ):
                return True
        except RuntimeError as ex:
            LOGGER.error("Login to Gigya failed: %s", ex)
        return False

    async def initialise(self, config_data):
        """Set up proxy."""
        if self._kamereon is None:
            raise RuntimeError("Please ensure Kamereon is initialised.")
        self._kamereon.set_account_id(config_data[CONF_KAMEREON_ACCOUNT_ID])
        vehicles = await self._hass.async_add_executor_job(self._kamereon.get_vehicles)
        self._vehicle_links = vehicles["vehicleLinks"]

    async def get_account_ids(self) -> list:
        """Get Kamereon account ids."""
        await self._hass.async_add_executor_job(self._gigya.account_info)

        accounts = []
        for account_details in await self._hass.async_add_executor_job(
            self._kamereon.get_accounts
        ):
            accounts.append(account_details["accountId"])
        return accounts

    @property
    def vehicle_links(self):
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
        async with self._vehicles_lock:
            pyze_vehicle_proxy = self._vehicle_proxies.get(vin)
            if pyze_vehicle_proxy is None:
                pyze_vehicle_proxy = PyZEVehicleProxy(
                    self._hass,
                    vehicle_link,
                    Vehicle(vehicle_link["vin"], self._kamereon),
                )
                self._vehicle_proxies[vin] = pyze_vehicle_proxy
                await pyze_vehicle_proxy.async_initialise()
        return self._vehicle_proxies[vin]
