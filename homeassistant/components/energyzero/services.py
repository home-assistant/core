"""The EnergyZero services."""

from datetime import date, datetime, timedelta
from enum import Enum, StrEnum
from functools import partial
from typing import Final
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, EnergyZeroNoDataError, Interval, PriceType
import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector, service
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnergyZeroConfigEntry, EnergyZeroDataUpdateCoordinator


class EnergyZeroService(StrEnum):
    """Store keys for EnergyZero services."""

    GET_GAS_PRICES = "get_gas_prices"
    GET_ENERGY_PRICES = "get_energy_prices"


class EnergyZeroServiceArgument(StrEnum):
    """Store keys for EnergyZero service arguments."""

    CONFIG_ENTRY = "config_entry"
    INCL_VAT = "incl_vat"
    START = "start"
    END = "end"
    PRICE_TYPE = "price_type"
    INTERVAL = "interval"


ENERGY_INTERVALS = {"hour": Interval.HOUR, "quarter": Interval.QUARTER}

SERVICE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(
            EnergyZeroServiceArgument.CONFIG_ENTRY
        ): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        probatio.Required(EnergyZeroServiceArgument.INCL_VAT): bool,
        probatio.Optional(EnergyZeroServiceArgument.START): str,
        probatio.Optional(EnergyZeroServiceArgument.END): str,
    }
)

ENERGY_SERVICE_SCHEMA: Final = SERVICE_SCHEMA.extend(
    {
        probatio.Optional(
            EnergyZeroServiceArgument.PRICE_TYPE, default="market"
        ): probatio.In(("market", "all_in")),
        probatio.Optional(
            EnergyZeroServiceArgument.INTERVAL, default="hour"
        ): probatio.In(ENERGY_INTERVALS),
    }
)


class ServicePriceType(Enum):
    """Type of service."""

    ENERGY = "energy"
    GAS = "gas"


def __get_date(
    date_input: str | None, local_tz: ZoneInfo
) -> tuple[date, datetime | None]:
    """Get date for the API and optional datetime for response filtering."""
    if not date_input:
        return dt_util.now().astimezone(local_tz).date(), None

    if date_value := dt_util.parse_date(date_input):
        return date_value, None

    if value := dt_util.parse_datetime(date_input):
        if value.tzinfo is None:
            value = value.replace(tzinfo=local_tz)
        else:
            value = value.astimezone(local_tz)
        return value.date(), dt_util.as_utc(value)

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


def __serialize_prices(
    prices: list[EnergyPrices], start: datetime, end: datetime
) -> ServiceResponse:
    """Filter and serialize prices to the requested datetime range."""
    unique_prices = {
        time_range: price
        for price_data in prices
        for time_range, price in price_data.prices.items()
    }
    return {
        "prices": [
            {
                "price": price,
                "timestamp": str(time_range.start_including),
                "start": str(time_range.start_including),
                "end": str(time_range.end_excluding),
            }
            for time_range, price in unique_prices.items()
            if time_range.end_excluding > start and time_range.start_including < end
        ]
    }


def __get_coordinator(call: ServiceCall) -> EnergyZeroDataUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry: EnergyZeroConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[EnergyZeroServiceArgument.CONFIG_ENTRY]
    )
    return entry.runtime_data


async def __get_prices(
    call: ServiceCall,
    *,
    price_type: ServicePriceType,
) -> ServiceResponse:
    coordinator = __get_coordinator(call)
    local_tz = ZoneInfo(call.hass.config.time_zone)
    start_date, start_datetime = __get_date(
        call.data.get(EnergyZeroServiceArgument.START), local_tz
    )
    end_date, end_datetime = __get_date(
        call.data.get(EnergyZeroServiceArgument.END), local_tz
    )

    filter_start = start_datetime or dt_util.as_utc(
        dt_util.start_of_local_day(start_date)
    )
    end_start = end_datetime or dt_util.as_utc(dt_util.start_of_local_day(end_date))

    if filter_start == end_start:
        day = filter_start.astimezone(local_tz).date()
        filter_start = dt_util.as_utc(dt_util.start_of_local_day(day))
        filter_end = dt_util.as_utc(dt_util.start_of_local_day(day + timedelta(days=1)))
    else:
        filter_end = end_datetime or dt_util.as_utc(
            dt_util.start_of_local_day(end_date + timedelta(days=1))
        )

    if filter_end <= filter_start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_range",
            translation_placeholders={
                "start": call.data.get(EnergyZeroServiceArgument.START)
                or start_date.isoformat(),
                "end": call.data.get(EnergyZeroServiceArgument.END)
                or end_date.isoformat(),
            },
        )

    selected_price_type = (
        PriceType.MARKET_WITH_VAT
        if call.data[EnergyZeroServiceArgument.INCL_VAT]
        else PriceType.MARKET
    )

    if (
        price_type is ServicePriceType.ENERGY
        and call.data[EnergyZeroServiceArgument.PRICE_TYPE] == "all_in"
    ):
        selected_price_type = (
            PriceType.ALL_IN
            if call.data[EnergyZeroServiceArgument.INCL_VAT]
            else PriceType.ALL_IN_EXCL_VAT
        )

    price_data: list[EnergyPrices] = []
    for day_offset in range((end_date - start_date).days + 1):
        request_date = start_date + timedelta(days=day_offset)
        if price_type is ServicePriceType.GAS:
            prices = coordinator.energyzero.get_gas_prices(
                start_date=request_date,
                end_date=request_date,
                price_type=selected_price_type,
                local_tz=local_tz,
            )
        else:
            prices = coordinator.energyzero.get_electricity_prices(
                start_date=request_date,
                end_date=request_date,
                interval=ENERGY_INTERVALS[
                    call.data[EnergyZeroServiceArgument.INTERVAL]
                ],
                price_type=selected_price_type,
                local_tz=local_tz,
            )

        try:
            price_data.append(await prices)
        except EnergyZeroNoDataError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={
                    "date": request_date.isoformat(),
                },
            ) from err

    return __serialize_prices(price_data, filter_start, filter_end)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up EnergyZero services."""

    hass.services.async_register(
        DOMAIN,
        EnergyZeroService.GET_GAS_PRICES,
        partial(__get_prices, price_type=ServicePriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        EnergyZeroService.GET_ENERGY_PRICES,
        partial(__get_prices, price_type=ServicePriceType.ENERGY),
        schema=ENERGY_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
