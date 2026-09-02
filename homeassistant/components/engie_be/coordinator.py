"""DataUpdateCoordinator for the ENGIE Belgium integration."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, override

from aioengiebelgium import (
    BusinessAgreement,
    EngieBeClient,
    EngieBeError,
    PricePeriod,
    PriceSlot,
    bare_ean,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, PRICES_SCAN_INTERVAL

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

_DIRECTIONS = ("offtake", "injection")
_DIRECTION_PREFIXES = ("OFFTAKE_", "INJECTION_")
_BLENDED_SLOT_CODE = "EN"


def _mask(identifier: str) -> str:
    """Mask an account/meter identifier down to its last four characters."""
    return f"…{identifier[-4:]}"


def normalize_slot_code(raw_code: str) -> str:
    """Strip a redundant direction prefix from a raw time-of-use slot code."""
    for prefix in _DIRECTION_PREFIXES:
        idx = raw_code.rfind(prefix)
        if idx != -1:
            return raw_code[idx + len(prefix) :]
    return raw_code


def _parse_date(value: str) -> date | None:
    """Parse a date or datetime string into a date."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _current_period(
    periods: tuple[PricePeriod, ...], today: date
) -> PricePeriod | None:
    """Return the price period covering today, if any."""
    for period in periods:
        from_date = _parse_date(period.valid_from)
        to_date = _parse_date(period.valid_to)
        if from_date is None or to_date is None:
            continue
        if from_date <= today < to_date:
            return period
    return None


@dataclass
class EngieBePricesData:
    """Pre-processed price lookup for one business agreement."""

    slots: dict[tuple[str, str, str], PriceSlot]
    eans: tuple[str, ...]


class EngieBeRelationsCoordinator(DataUpdateCoordinator[dict[str, BusinessAgreement]]):
    """Coordinator that tracks the account's active business agreements."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
    ) -> None:
        """Initialize the relations coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_relations",
        )
        self.client = client

    @override
    async def _async_update_data(self) -> dict[str, BusinessAgreement]:
        """Fetch the account's active business agreements."""
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
        return agreements


class EngieBePricesCoordinator(DataUpdateCoordinator[EngieBePricesData]):
    """Coordinator that fetches energy prices for one business agreement."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
        ban: str,
        agreement: BusinessAgreement,
    ) -> None:
        """Initialize the prices coordinator for one business agreement."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_prices_{_mask(ban)}",
            update_interval=PRICES_SCAN_INTERVAL,
        )
        self.client = client
        self.ban = ban
        self.agreement = agreement
        self.ean_energy_types: dict[str, str | None] = {}
        device_name = (
            agreement.consumption_address.format()
            if agreement.consumption_address is not None
            else ""
        ) or ban
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, ban)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ENGIE Belgium",
            name=device_name,
        )

    @override
    async def _async_update_data(self) -> EngieBePricesData:
        """Fetch this household's prices and pre-process them into a slot lookup."""
        try:
            prices = await self.client.async_get_prices(self.ban)
        except EngieBeError as err:
            raise UpdateFailed(str(err)) from err

        new_eans = list(
            dict.fromkeys(
                ean_prices.ean
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
                if isinstance(service_point_result, EngieBeError):
                    LOGGER.debug(
                        "Fetching service point for %s failed: %s",
                        _mask(bare_ean(ean)),
                        service_point_result,
                    )
                    continue
                if isinstance(service_point_result, BaseException):
                    raise service_point_result
                self.ean_energy_types.update(service_point_result.ean_energy_types)
                self.ean_energy_types.setdefault(bare_ean(ean), None)

        today = dt_util.now().date()
        slots: dict[tuple[str, str, str], PriceSlot] = {}
        for ean_prices in prices.items:
            period = _current_period(ean_prices.periods, today)
            if period is None:
                continue
            for direction in _DIRECTIONS:
                direction_slots = (
                    period.offtake if direction == "offtake" else period.injection
                )
                for slot in direction_slots:
                    normalized = normalize_slot_code(slot.time_of_use_slot_code)
                    if normalized == _BLENDED_SLOT_CODE:
                        continue
                    slots[ean_prices.ean, direction, slot.time_of_use_slot_code] = slot

        return EngieBePricesData(
            slots=slots,
            eans=tuple(ean_prices.ean for ean_prices in prices.items),
        )
