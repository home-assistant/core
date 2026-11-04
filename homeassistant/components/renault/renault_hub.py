"""Proxy to handle account communication with Renault servers."""

import asyncio
from collections.abc import Callable
import contextlib
from datetime import timedelta
import logging
from time import time
from typing import TYPE_CHECKING

import aiohttp
from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidCredentialsException,
    PendingTwoFactorAuthenticationException,
)
from renault_api.gigya.models import GigyaTfaEmail
from renault_api.kamereon.exceptions import KamereonResponseException
from renault_api.kamereon.models import KamereonVehiclesLink
from renault_api.renault_account import RenaultAccount
from renault_api.renault_client import RenaultClient

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    COOLING_UPDATES_SECONDS,
    DOMAIN,
    MAX_CALLS_PER_HOURS,
    RenaultConfigurationKeys,
)
from .coordinator import RenaultVehicleListCoordinator
from .renault_vehicle import COORDINATORS, RenaultVehicleProxy

if TYPE_CHECKING:
    from . import RenaultConfigEntry

LOGGER = logging.getLogger(__name__)


async def _get_filtered_vehicles(account: RenaultAccount) -> list[KamereonVehiclesLink]:
    """Get the vehicles, filtering out those with missing details."""
    vehicles = await account.get_vehicles()
    return await _filter_vehicles_with_details(
        account, vehicles.vehicleLinks or [], set()
    )


async def _filter_vehicles_with_details(
    account: RenaultAccount,
    vehicle_links: list[KamereonVehiclesLink],
    missing_details_vins: set[str | None],
) -> list[KamereonVehiclesLink]:
    """Filter out the vehicles with missing details.

    The vehicle list sometimes omits the details, so they are requested
    separately. They may still be missing for new purchases, or due to an
    issue with the Renault servers. A warning is logged once for each vehicle,
    `missing_details_vins` keeps track of the vehicles already logged.
    """
    result: list[KamereonVehiclesLink] = []
    for link in vehicle_links:
        if link.vehicleDetails is None and link.vin:
            vehicle = await account.get_api_vehicle(link.vin)
            with contextlib.suppress(KamereonResponseException):
                link.vehicleDetails = await vehicle.get_details()
        if link.vehicleDetails is None:
            if link.vin in missing_details_vins:
                LOGGER.debug("Ignoring vehicle with missing details: %s", link.vin)
            else:
                LOGGER.warning("Ignoring vehicle with missing details: %s", link.vin)
                missing_details_vins.add(link.vin)
            continue
        result.append(link)
    return result


def _get_scan_interval(num_call_per_scan: int) -> timedelta:
    """Get the scan interval that keeps the calls within the hourly limit."""
    # One call per hour is kept for the vehicle list.
    return timedelta(seconds=(3600 * num_call_per_scan) / (MAX_CALLS_PER_HOURS - 1))


class RenaultHub:
    """Handle account communication with Renault servers."""

    def __init__(self, hass: HomeAssistant, locale: str) -> None:
        """Initialise proxy."""
        self._hass = hass
        self._client = RenaultClient(
            websession=async_get_clientsession(self._hass), locale=locale
        )
        self._account: RenaultAccount | None = None
        self._config_entry: RenaultConfigEntry | None = None
        self._vehicles: dict[str, RenaultVehicleProxy] = {}
        self._vehicle_listeners: list[Callable[[RenaultVehicleProxy], None]] = []
        self._vehicles_lock = asyncio.Lock()
        self._missing_details_vins: set[str | None] = set()

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

        self._config_entry = config_entry
        self._account = await self._client.get_api_account(account_id)
        vehicles = await self._account.get_vehicles()
        all_vehicle_links = vehicles.vehicleLinks or []
        vehicle_links = await _filter_vehicles_with_details(
            self._account, all_vehicle_links, self._missing_details_vins
        )
        # An empty list is more likely a server issue than all vehicles removed.
        if vins := {link.vin for link in all_vehicle_links if link.vin}:
            self._async_remove_stale_devices(config_entry, vins)
        if not vehicle_links:
            LOGGER.debug(
                "No valid vehicle details found for account_id: %s", account_id
            )
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_vehicle_details",
            )

        await self._async_add_vehicles(vehicle_links)

        vehicle_list = RenaultVehicleListCoordinator(
            self._hass, config_entry, self, self._account
        )
        vehicle_list.async_set_updated_data(all_vehicle_links)
        config_entry.async_on_unload(
            vehicle_list.async_add_listener(
                lambda: self._async_vehicle_list_updated(vehicle_list.data)
            )
        )

    async def _async_add_vehicles(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Set up vehicles and adjust the scan interval of all vehicles."""
        assert self._account is not None
        assert self._config_entry is not None
        # Assume all coordinators until the endpoints of the new vehicles are checked.
        scan_interval = _get_scan_interval(
            sum(len(vehicle.coordinators) for vehicle in self._vehicles.values())
            + len(COORDINATORS) * len(vehicle_links)
        )

        device_registry = dr.async_get(self._hass)
        results = await asyncio.gather(
            *(
                self.async_initialise_vehicle(
                    vehicle_link,
                    self._account,
                    scan_interval,
                    self._config_entry,
                    device_registry,
                )
                for vehicle_link in vehicle_links
            ),
            return_exceptions=True,
        )
        self._async_update_scan_interval()
        for result in results:
            if isinstance(result, BaseException):
                raise result

    @callback
    def _async_update_scan_interval(self) -> None:
        """Set the scan interval of all vehicles from their active coordinators."""
        scan_interval = _get_scan_interval(
            sum(len(vehicle.coordinators) for vehicle in self._vehicles.values())
        )
        for vehicle in self._vehicles.values():
            vehicle.update_scan_interval(scan_interval)

    @callback
    def _async_vehicle_list_updated(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Add and remove vehicles when the vehicle list changes."""
        # Listeners are also called with the previous list while throttled.
        if self.is_throttled():
            return
        if {link.vin for link in vehicle_links if link.vin} == set(self._vehicles):
            return
        assert self._config_entry is not None
        self._config_entry.async_create_background_task(
            self._hass,
            self._async_update_vehicles(vehicle_links),
            "renault_update_vehicles",
        )

    async def _async_update_vehicles(
        self, vehicle_links: list[KamereonVehiclesLink]
    ) -> None:
        """Add new vehicles and remove the vehicles no longer in the account."""
        assert self._account is not None
        assert self._config_entry is not None
        async with self._vehicles_lock:
            # An empty list is more likely a server issue than all vehicles removed.
            if vins := {link.vin for link in vehicle_links if link.vin}:
                self._async_remove_stale_devices(self._config_entry, vins)
                for vin in set(self._vehicles) - vins:
                    vehicle = self._vehicles.pop(vin)
                    for coordinator in vehicle.coordinators.values():
                        await coordinator.async_shutdown()
                self._async_update_scan_interval()

            try:
                new_vehicle_links = await _filter_vehicles_with_details(
                    self._account,
                    [
                        link
                        for link in vehicle_links
                        if link.vin and link.vin not in self._vehicles
                    ],
                    self._missing_details_vins,
                )
                if new_vehicle_links:
                    await self._async_add_vehicles(new_vehicle_links)
            except ConfigEntryAuthFailed, NotAuthenticatedException:
                self._config_entry.async_start_reauth(self._hass)
            except (aiohttp.ClientError, TimeoutError, GigyaException) as err:
                LOGGER.debug(
                    "Failed to update the vehicles, retrying at the next check: %s",
                    err,
                )

    @callback
    def _async_remove_stale_devices(
        self, config_entry: RenaultConfigEntry, vins: set[str]
    ) -> None:
        """Remove the devices of vehicles no longer linked to the account."""
        device_registry = dr.async_get(self._hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            if not any(
                domain == DOMAIN and identifier in vins
                for domain, identifier in device_entry.identifiers
            ):
                device_registry.async_remove_device(device_entry.id)

    @callback
    def async_add_vehicle_listener(
        self, add_vehicle: Callable[[RenaultVehicleProxy], None]
    ) -> CALLBACK_TYPE:
        """Call add_vehicle for the current vehicles and each vehicle added later."""
        for vehicle in self._vehicles.values():
            add_vehicle(vehicle)
        self._vehicle_listeners.append(add_vehicle)
        return lambda: self._vehicle_listeners.remove(add_vehicle)

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
        for add_vehicle in self._vehicle_listeners:
            add_vehicle(vehicle)

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
