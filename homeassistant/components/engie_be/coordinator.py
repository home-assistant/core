"""DataUpdateCoordinator for the ENGIE Belgium integration."""

import asyncio
from typing import TYPE_CHECKING, override

from aioengiebelgium import (
    BusinessAgreement,
    EngieBeAuthenticationError,
    EngieBeClient,
    EngieBeError,
    PricesResponse,
    bare_ean,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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


class EngieBePricesCoordinator(DataUpdateCoordinator[dict[str, PricesResponse]]):
    """Coordinator that fetches ENGIE Belgium energy prices for every business agreement."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
        business_agreement_numbers: list[str],
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
        self.business_agreement_numbers = business_agreement_numbers
        self.ean_energy_types: dict[str, str | None] = {}

    @override
    async def _async_update_data(self) -> dict[str, PricesResponse]:
        """Fetch prices for every business agreement."""
        results = await asyncio.gather(
            *(
                self.client.async_get_prices(ban)
                for ban in self.business_agreement_numbers
            ),
            return_exceptions=True,
        )
        data: dict[str, PricesResponse] = {}
        first_error: EngieBeError | None = None
        any_success = False
        for ban, result in zip(self.business_agreement_numbers, results, strict=True):
            if isinstance(result, EngieBeAuthenticationError):
                raise ConfigEntryAuthFailed from result
            if isinstance(result, EngieBeError):
                first_error = first_error or result
                if self.data is not None and ban in self.data:
                    LOGGER.warning(
                        "Fetching prices for %s failed: %s", _mask(ban), result
                    )
                    data[ban] = self.data[ban]
                else:
                    LOGGER.warning(
                        "Fetching prices for %s failed and no previous data is"
                        " available: %s",
                        _mask(ban),
                        result,
                    )
                continue
            if isinstance(result, BaseException):
                raise result
            any_success = True
            data[ban] = result

        if first_error is not None and not any_success:
            raise UpdateFailed(str(first_error)) from first_error

        new_eans = list(
            dict.fromkeys(
                ean_prices.ean
                for prices in data.values()
                for ean_prices in prices.items
                if bare_ean(ean_prices.ean) not in self.ean_energy_types
            )
        )
        if new_eans:
            service_points = await asyncio.gather(
                *(self.client.async_get_service_point(ean) for ean in new_eans),
                return_exceptions=True,
            )
            for ean, service_point_result in zip(new_eans, service_points, strict=True):
                if isinstance(service_point_result, EngieBeAuthenticationError):
                    raise ConfigEntryAuthFailed from service_point_result
                if isinstance(service_point_result, EngieBeError):
                    LOGGER.debug(
                        "Fetching service point for %s failed: %s",
                        _mask(ean),
                        service_point_result,
                    )
                    self.ean_energy_types.setdefault(bare_ean(ean), None)
                    continue
                if isinstance(service_point_result, BaseException):
                    raise service_point_result
                self.ean_energy_types.update(service_point_result.ean_energy_types)

        return data
