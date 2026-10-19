"""Proxy to handle account communication with Renault servers."""

import asyncio
import contextlib
from datetime import timedelta
import logging
from time import time
from typing import TYPE_CHECKING

from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya.exceptions import (
    InvalidCredentialsException,
    PendingTwoFactorAuthenticationException,
)
from renault_api.gigya.models import GigyaTfaEmail
from renault_api.kamereon.exceptions import KamereonResponseException
from renault_api.kamereon.models import KamereonVehiclesLink
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    COOLING_UPDATES_SECONDS,
    MAX_CALLS_PER_HOURS,
    RenaultConfigurationKeys,
)
from .renault_vehicle import COORDINATORS, RenaultVehicleProxy

if TYPE_CHECKING:
    from . import RenaultConfigEntry

LOGGER = logging.getLogger(__name__)


async def _get_filtered_vehicles(account: RenaultAccount) -> list[KamereonVehiclesLink]:
    """Get the vehicles, filtering out those with missing details.

    The vehicle list sometimes omits the details, so they are requested
    separately. They may still be missing for new purchases, or due to an
    issue with the Renault servers.
    """
    vehicles = await account.get_vehicles()
    if not vehicles.vehicleLinks:
        return []
    result: list[KamereonVehiclesLink] = []
    for link in vehicles.vehicleLinks:
        if link.vehicleDetails is None and link.vin:
            vehicle = await account.get_api_vehicle(link.vin)
            with contextlib.suppress(KamereonResponseException):
                link.vehicleDetails = await vehicle.get_details()
        if link.vehicleDetails is None:
            LOGGER.warning("Ignoring vehicle with missing details: %s", link.vin)
            continue
        result.append(link)
    return result


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

    @property
    def login_token(self) -> str | None:
        """Return the Gigya login token obtained from a successful login."""
        return self._client.session.login_token

    @property
    def device_ids(self) -> dict[str, str]:
        """Return the Gigya device ids remembered after two-factor authentication."""
        return self._client.session.device_ids

    def set_device_ids(self, device_ids: dict[str, str]) -> None:
        """Restore Gigya device ids, so a remembered device skips two-factor auth."""
        self._client.session.set_device_ids(device_ids)

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

    async def get_two_factor_auth_emails(self) -> list[GigyaTfaEmail]:
        """Get the email addresses registered for two-factor authentication."""
        return await self._client.session.get_two_factor_auth_emails()

    async def request_two_factor_auth_code(self, email_id: str) -> None:
        """Email a two-factor authentication code."""
        await self._client.session.request_two_factor_auth_code(email_id)

    async def complete_two_factor_auth(self, code: str) -> None:
        """Complete the pending login with the emailed code."""
        await self._client.session.complete_two_factor_auth(code)

    async def async_login(self, config_entry: RenaultConfigEntry) -> None:
        """Log in with the stored login token, or fall back to the password."""
        if login_token := config_entry.data.get(RenaultConfigurationKeys.LOGIN_TOKEN):
            self._client.session.set_login_token(login_token)
            return
        self.set_device_ids(
            config_entry.data.get(RenaultConfigurationKeys.DEVICE_IDS, {})
        )
        try:
            login_success = await self.attempt_login(
                config_entry.data[RenaultConfigurationKeys.USERNAME],
                config_entry.data[RenaultConfigurationKeys.PASSWORD],
            )
        except PendingTwoFactorAuthenticationException as exc:
            # The code can only be entered in the reauth flow.
            raise NotAuthenticatedException from exc
        if login_success:
            # Persist the login token so the next setup can skip the password.
            self._hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    RenaultConfigurationKeys.LOGIN_TOKEN: self.login_token,
                },
            )
        else:
            raise NotAuthenticatedException

    async def async_initialise(self, config_entry: RenaultConfigEntry) -> None:
        """Set up proxy."""
        await self.async_login(config_entry)

        account_id: str = config_entry.data[
            RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID
        ]

        self._account = await self._client.get_api_account(account_id)
        vehicle_links = await _get_filtered_vehicles(self._account)
        if not vehicle_links:
            LOGGER.debug(
                "No valid vehicle details found for account_id: %s", account_id
            )
            raise ConfigEntryNotReady(
                "Failed to retrieve vehicle details from Renault servers"
            )

        num_call_per_scan = len(COORDINATORS) * len(vehicle_links)
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
                for vehicle_link in vehicle_links
            )
        )

        # all vehicles have been initiated with the right number of active coordinators
        num_call_per_scan = 0
        for vehicle_link in vehicle_links:
            vehicle = self._vehicles[str(vehicle_link.vin)]
            num_call_per_scan += len(vehicle.coordinators)

        new_scan_interval = timedelta(
            seconds=(3600 * num_call_per_scan) / MAX_CALLS_PER_HOURS
        )
        if new_scan_interval != scan_interval:
            # we need to change the vehicles with the right scan interval
            for vehicle_link in vehicle_links:
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
            identifiers=vehicle.device_info.identifiers,
            manufacturer=vehicle.device_info.manufacturer,
            name=vehicle.device_info.name,
            model=vehicle.device_info.model,
            model_id=vehicle.device_info.model_id,
            sw_version=None,  # cleanup from PR #125399
        )
        self._vehicles[vehicle_link.vin] = vehicle

    async def get_account_ids(self) -> list[str]:
        """Get Kamereon account ids."""
        accounts = []
        for account in await self._client.get_api_accounts():
            vehicle_links = await _get_filtered_vehicles(account)

            # Only add the account if it has linked vehicles.
            if vehicle_links:
                accounts.append(account.account_id)
        return accounts

    async def get_all_account_ids(self) -> list[str]:
        """Get all Kamereon account ids, including those without vehicles."""
        return [account.account_id for account in await self._client.get_api_accounts()]

    async def get_account_ids_for_vins(self, vins: set[str]) -> list[str]:
        """Get Kamereon account ids linked to any of the given vehicles."""
        accounts = []
        for account in await self._client.get_api_accounts():
            vehicle_links = await _get_filtered_vehicles(account)
            if any(link.vin in vins for link in vehicle_links):
                accounts.append(account.account_id)
        return accounts

    @property
    def vehicles(self) -> dict[str, RenaultVehicleProxy]:
        """Get list of vehicles."""
        return self._vehicles
