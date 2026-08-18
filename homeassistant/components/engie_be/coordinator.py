"""DataUpdateCoordinator for the ENGIE Belgium integration."""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from aioengiebelgium import (
    BusinessAgreement,
    EngieBeClient,
    EngieBeError,
    PricesResponse,
    bare_ean,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

if TYPE_CHECKING:
    from . import EngieBeConfigEntry


def _mask(identifier: str) -> str:
    """Mask an account/meter identifier down to its last four characters."""
    return f"…{identifier[-4:]}"


def household_device_info(ban: str, agreement: BusinessAgreement) -> DeviceInfo:
    """Build the shared household device identity for a business agreement."""
    device_name = (
        agreement.consumption_address.format()
        if agreement.consumption_address is not None
        else ban
    )
    return DeviceInfo(
        identifiers={(DOMAIN, ban)},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="ENGIE Belgium",
        name=device_name,
    )


@dataclass
class EngieBeHouseholdData:
    """Fetched data for one business agreement."""

    agreement: BusinessAgreement
    prices: PricesResponse


class EngieBePricesCoordinator(DataUpdateCoordinator[dict[str, EngieBeHouseholdData]]):
    """Coordinator that fetches ENGIE Belgium energy prices for every business agreement."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.ean_energy_types: dict[str, str | None] = {}
        self._logged_failures: set[str] = set()

    @override
    async def _async_update_data(self) -> dict[str, EngieBeHouseholdData]:
        """Fetch relations and prices for every active business agreement."""
        try:
            relations = await self.client.async_get_customer_account_relations()
        except EngieBeError as err:
            raise UpdateFailed(str(err)) from err

        agreements = {
            agreement.business_agreement_number: agreement
            for account in relations.accounts
            for agreement in account.customer_account.business_agreements
            if agreement.active
        }
        if not agreements:
            LOGGER.debug("No active business agreements found")

        results = await asyncio.gather(
            *(self.client.async_get_prices(ban) for ban in agreements),
            return_exceptions=True,
        )
        data: dict[str, EngieBeHouseholdData] = {}
        first_error: EngieBeError | None = None
        any_success = False
        for ban, result in zip(agreements, results, strict=True):
            if isinstance(result, EngieBeError):
                first_error = first_error or result
                had_data = self.data is not None and ban in self.data
                if ban in self._logged_failures:
                    LOGGER.debug(
                        "Fetching prices for %s still failing: %s", _mask(ban), result
                    )
                elif had_data:
                    LOGGER.warning(
                        "Fetching prices for %s failed: %s", _mask(ban), result
                    )
                else:
                    LOGGER.warning(
                        "Fetching prices for %s failed and no previous data is"
                        " available: %s",
                        _mask(ban),
                        result,
                    )
                self._logged_failures.add(ban)
                if had_data:
                    data[ban] = EngieBeHouseholdData(
                        agreement=agreements[ban], prices=self.data[ban].prices
                    )
                continue
            if isinstance(result, BaseException):
                raise result
            any_success = True
            if ban in self._logged_failures:
                LOGGER.info("Fetching prices for %s recovered", _mask(ban))
                self._logged_failures.discard(ban)
            data[ban] = EngieBeHouseholdData(agreement=agreements[ban], prices=result)

        if first_error is not None and not any_success:
            raise UpdateFailed(str(first_error)) from first_error

        new_eans = list(
            dict.fromkeys(
                ean_prices.ean
                for household in data.values()
                for ean_prices in household.prices.items
                if bare_ean(ean_prices.ean) not in self.ean_energy_types
            )
        )
        if new_eans:
            service_points = await asyncio.gather(
                *(self.client.async_get_service_point(ean) for ean in new_eans),
                return_exceptions=True,
            )
            for ean, service_point_result in zip(new_eans, service_points, strict=True):
                if isinstance(service_point_result, EngieBeError):
                    LOGGER.debug(
                        "Fetching service point for %s failed: %s",
                        _mask(ean),
                        service_point_result,
                    )
                    continue
                if isinstance(service_point_result, BaseException):
                    raise service_point_result
                self.ean_energy_types.update(service_point_result.ean_energy_types)
                self.ean_energy_types.setdefault(bare_ean(ean), None)

        return data
