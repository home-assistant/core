"""DataUpdateCoordinator for the ENGIE Belgium integration."""

import asyncio
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, override
from zoneinfo import ZoneInfo

from aioengiebelgium import (
    BusinessAgreement,
    EngieBeAuthenticationError,
    EngieBeClient,
    EngieBeError,
    EpexGranularity,
    EpexSlot,
    MonthlyPeaks,
    Peak,
    PricePeriod,
    PriceSlot,
    ServicePoint,
    bare_ean,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EPEX_SCAN_INTERVAL,
    LOGGER,
    PEAKS_SCAN_INTERVAL,
    PRICES_SCAN_INTERVAL,
)

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

_DIRECTIONS = ("offtake", "injection")
_DIRECTION_PREFIXES = ("OFFTAKE_", "INJECTION_")
_BLENDED_SLOT_CODE = "EN"
_SERVICE_POINT_REFRESH_INTERVAL = timedelta(days=1)

BRUSSELS_TIME_ZONE = ZoneInfo("Europe/Brussels")


def mask_identifier(identifier: str) -> str:
    """Mask an account/meter identifier down to its last four characters."""
    return f"…{identifier[-4:]}"


def invalid_auth_error() -> ConfigEntryAuthFailed:
    """Return the error that asks the user to sign in again."""
    return ConfigEntryAuthFailed(
        translation_domain=DOMAIN, translation_key="invalid_auth"
    )


def _cannot_connect() -> UpdateFailed:
    """Return the error for a failed fetch from ENGIE."""
    return UpdateFailed(translation_domain=DOMAIN, translation_key="cannot_connect")


@contextmanager
def _raise_update_errors() -> Iterator[None]:
    """Turn client errors into the matching coordinator update errors."""
    try:
        yield
    except EngieBeAuthenticationError as err:
        raise invalid_auth_error() from err
    except EngieBeError as err:
        raise _cannot_connect() from err


def normalize_slot_code(raw_code: str) -> str:
    """Strip a redundant direction prefix from a raw time-of-use slot code."""
    for prefix in _DIRECTION_PREFIXES:
        idx = raw_code.rfind(prefix)
        if idx != -1:
            return raw_code[idx + len(prefix) :]
    return raw_code


def _current_period(
    periods: tuple[PricePeriod, ...], today: date
) -> PricePeriod | None:
    """Return the price period covering today, if any."""
    for period in periods:
        if period.contains(today):
            return period
    return None


def _gas_conversion_coefficient(service_point: ServicePoint) -> float | None:
    """Return the kWh per m³ conversion factor of a gas service point, if any."""
    if (
        service_point.market_details is None
        or service_point.market_details.installation is None
    ):
        return None
    coefficient = service_point.market_details.installation.gas_conversion_coefficient
    if coefficient is None or coefficient <= 0:
        return None
    return coefficient


@dataclass
class EngieBePricesData:
    """Pre-processed price lookup for one business agreement."""

    slots: dict[tuple[str, str, str], PriceSlot]
    eans: tuple[str, ...]
    gas_conversion_coefficients: dict[str, float] = field(default_factory=dict)


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
        with _raise_update_errors():
            relations = await self.client.async_get_customer_account_relations()

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
            name=f"{DOMAIN}_prices_{mask_identifier(ban)}",
            update_interval=PRICES_SCAN_INTERVAL,
        )
        self.client = client
        self.ban = ban
        self.ean_energy_types: dict[str, str | None] = {}
        self.gas_conversion_coefficients: dict[str, float] = {}
        self._service_points_refreshed_at: dict[str, datetime] = {}
        address = (
            agreement.consumption_address.format()
            if agreement.consumption_address is not None
            else ""
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, ban)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ENGIE Belgium",
            name=address or None,
            translation_key=None if address else "business_agreement",
            translation_placeholders={"ban": mask_identifier(ban)},
        )

    def _service_point_due(self, ean: str, now: datetime) -> bool:
        """Return True when the service point of a bare EAN needs a fresh fetch."""
        refreshed_at = self._service_points_refreshed_at.get(ean)
        return (
            refreshed_at is None
            or now - refreshed_at >= _SERVICE_POINT_REFRESH_INTERVAL
        )

    @override
    async def _async_update_data(self) -> EngieBePricesData:
        """Fetch this household's prices and pre-process them into a slot lookup."""
        with _raise_update_errors():
            prices = await self.client.async_get_prices(self.ban)

        now = dt_util.utcnow()
        raw_ean_by_bare: dict[str, str] = {}
        for ean_prices in prices.items:
            if self._service_point_due(bare := bare_ean(ean_prices.ean), now):
                raw_ean_by_bare.setdefault(bare, ean_prices.ean)
        if raw_ean_by_bare:
            service_points = await asyncio.gather(
                *(
                    self.client.async_get_service_point(ean)
                    for ean in raw_ean_by_bare.values()
                ),
                return_exceptions=True,
            )
            for bare, service_point_result in zip(
                raw_ean_by_bare, service_points, strict=True
            ):
                if isinstance(service_point_result, EngieBeAuthenticationError):
                    raise invalid_auth_error() from service_point_result
                if isinstance(service_point_result, EngieBeError):
                    LOGGER.debug(
                        "Fetching service point for %s failed: %s",
                        mask_identifier(bare),
                        service_point_result,
                    )
                    continue
                if isinstance(service_point_result, BaseException):
                    raise service_point_result
                self.ean_energy_types.update(service_point_result.ean_energy_types)
                self.ean_energy_types.setdefault(bare, None)
                if (
                    coefficient := _gas_conversion_coefficient(service_point_result)
                ) is None:
                    self.gas_conversion_coefficients.pop(bare, None)
                else:
                    self.gas_conversion_coefficients[bare] = coefficient
                self._service_points_refreshed_at[bare] = now

        brussels = dt_util.get_time_zone("Europe/Brussels")
        assert brussels is not None
        today = dt_util.now(brussels).date()
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
            gas_conversion_coefficients=dict(self.gas_conversion_coefficients),
        )


@dataclass(frozen=True)
class EngieBeEpexData:
    """Merged EPEX day-ahead price slots covering today and tomorrow."""

    hourly: tuple[EpexSlot, ...]
    quarter_hourly: tuple[EpexSlot, ...]

    def slots(self, granularity: EpexGranularity) -> tuple[EpexSlot, ...]:
        """Return the merged slots for one granularity."""
        return {
            EpexGranularity.HOURLY: self.hourly,
            EpexGranularity.QUARTER_HOURLY: self.quarter_hourly,
        }[granularity]


def epex_slots_for_day(slots: Iterable[EpexSlot], day: date) -> tuple[EpexSlot, ...]:
    """Return the EPEX slots that start on the given Brussels calendar day."""
    return tuple(
        slot
        for slot in slots
        if slot.start.astimezone(BRUSSELS_TIME_ZONE).date() == day
    )


def epex_slot_covering(slots: Iterable[EpexSlot], moment: datetime) -> EpexSlot | None:
    """Return the EPEX slot that covers the given aware moment."""
    return next((slot for slot in slots if slot.start <= moment < slot.end), None)


def epex_window(day: date) -> tuple[datetime, datetime]:
    """Return the Brussels-local start and end of one calendar day."""
    start = datetime.combine(day, time(), tzinfo=BRUSSELS_TIME_ZONE)
    return start, start + timedelta(days=1)


def epex_slots_cover_day(
    slots: Iterable[EpexSlot], day: date, granularity: EpexGranularity
) -> bool:
    """Return True when the slots tile the Brussels calendar day without gaps."""
    start, end = epex_window(day)
    duration = timedelta(minutes=granularity.value)
    day_slots = sorted(epex_slots_for_day(slots, day), key=lambda slot: slot.start)
    if not day_slots or day_slots[0].start != start or day_slots[-1].end != end:
        return False
    if any(slot.end - slot.start != duration for slot in day_slots):
        return False
    return all(slot.end == following.start for slot, following in pairwise(day_slots))


def epex_day_available(data: EngieBeEpexData, day: date) -> bool:
    """Return True when both granularities fully cover the given day."""
    return all(
        epex_slots_cover_day(data.slots(granularity), day, granularity)
        for granularity in EpexGranularity
    )


@dataclass(frozen=True)
class EngieBePeaksData:
    """Capacity tariff peaks of one business agreement."""

    monthly: MonthlyPeaks
    previous_month: MonthlyPeaks | None

    @property
    def peak(self) -> Peak | None:
        """Return the peak to display, falling back to the previous month early in the month."""
        if self.monthly.peak_of_the_month is not None:
            return self.monthly.peak_of_the_month
        if self.previous_month is not None:
            return self.previous_month.peak_of_the_month
        return None

    @property
    def is_fallback(self) -> bool:
        """Return True when the displayed peak belongs to the previous month."""
        return self.monthly.peak_of_the_month is None and self.peak is not None

    @property
    def peak_month(self) -> str | None:
        """Return the YYYY-MM month the displayed peak belongs to."""
        if self.monthly.peak_of_the_month is not None:
            source = self.monthly
        elif (
            self.previous_month is not None
            and self.previous_month.peak_of_the_month is not None
        ):
            source = self.previous_month
        else:
            return None
        return f"{source.year}-{source.month:02d}"


class EngieBePeaksCoordinator(DataUpdateCoordinator[EngieBePeaksData]):
    """Coordinator that fetches capacity tariff peaks for one business agreement."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
        ban: str,
    ) -> None:
        """Initialize the peaks coordinator for one business agreement."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_peaks_{mask_identifier(ban)}",
            update_interval=PEAKS_SCAN_INTERVAL,
        )
        self.client = client
        self.ban = ban

    @override
    async def _async_update_data(self) -> EngieBePeaksData:
        """Fetch this month's peaks, plus last month's when this month has no peak yet."""
        today = dt_util.now(BRUSSELS_TIME_ZONE).date()
        with _raise_update_errors():
            monthly = await self.client.async_get_monthly_peaks(
                self.ban, today.year, today.month
            )
            previous_month: MonthlyPeaks | None = None
            if monthly.peak_of_the_month is None:
                prev_year, prev_month = (
                    (today.year - 1, 12)
                    if today.month == 1
                    else (today.year, today.month - 1)
                )
                previous_month = await self.client.async_get_monthly_peaks(
                    self.ban, prev_year, prev_month
                )
        return EngieBePeaksData(monthly=monthly, previous_month=previous_month)


class EngieBeEpexCoordinator(DataUpdateCoordinator[EngieBeEpexData]):
    """Coordinator that fetches Belgian EPEX day-ahead prices for both granularities."""

    config_entry: EngieBeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EngieBeConfigEntry,
        client: EngieBeClient,
    ) -> None:
        """Initialize the EPEX coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_epex",
            update_interval=EPEX_SCAN_INTERVAL,
        )
        self.client = client
        self.data = EngieBeEpexData(hourly=(), quarter_hourly=())
        self._listener_unsub: Callable[[], None] | None = None

    @callback
    def _async_quarter_hour_tick(self, _now: datetime) -> None:
        """Notify the entities on every quarter-hour boundary."""
        self.async_update_listeners()

    @override
    async def async_shutdown(self) -> None:
        """Cancel the quarter-hour listener timer and shut down."""
        if self._listener_unsub is not None:
            self._listener_unsub()
            self._listener_unsub = None
        await super().async_shutdown()

    @override
    async def _async_setup(self) -> None:
        """Start the quarter-hour listener timer."""
        self._listener_unsub = async_track_utc_time_change(
            self.hass,
            self._async_quarter_hour_tick,
            minute=(0, 15, 30, 45),
            second=0,
        )

    @override
    async def _async_update_data(self) -> EngieBeEpexData:
        """Fetch EPEX prices for each day and granularity without full coverage."""
        today = dt_util.now(BRUSSELS_TIME_ZONE).date()
        tomorrow = today + timedelta(days=1)
        slots = {
            granularity: [
                slot
                for slot in self.data.slots(granularity)
                if slot.start.astimezone(BRUSSELS_TIME_ZONE).date() >= today
            ]
            for granularity in EpexGranularity
        }
        for day, required in ((today, True), (tomorrow, False)):
            for granularity in EpexGranularity:
                if epex_slots_cover_day(slots[granularity], day, granularity):
                    continue
                try:
                    payload = await self.client.async_get_epex_prices(
                        *epex_window(day), granularity=granularity
                    )
                except EngieBeAuthenticationError as err:
                    raise invalid_auth_error() from err
                except EngieBeError as err:
                    if required:
                        raise _cannot_connect() from err
                    LOGGER.debug("Fetching EPEX prices for %s failed: %s", day, err)
                    continue
                slots[granularity] = [
                    slot
                    for slot in slots[granularity]
                    if slot.start.astimezone(BRUSSELS_TIME_ZONE).date() != day
                ] + list(payload.slots)
        return EngieBeEpexData(
            hourly=tuple(
                sorted(slots[EpexGranularity.HOURLY], key=lambda slot: slot.start)
            ),
            quarter_hourly=tuple(
                sorted(
                    slots[EpexGranularity.QUARTER_HOURLY],
                    key=lambda slot: slot.start,
                )
            ),
        )
