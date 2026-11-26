"""Services for Tibber integration."""

import datetime as dt
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

import aiohttp
import probatio
import tibber

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .const import TibberConfigEntry


class TibberService(StrEnum):
    """Store keys for Tibber services."""

    GET_PRICES = "get_prices"


class TibberServiceArgument(StrEnum):
    """Store keys for Tibber service arguments."""

    START = "start"
    END = "end"


SERVICE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Optional(TibberServiceArgument.START): str,
        probatio.Optional(TibberServiceArgument.END): str,
    }
)


async def __get_prices(call: ServiceCall) -> ServiceResponse:
    entries: list[TibberConfigEntry] = call.hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry",
        )
    tibber_connection = await entries[0].runtime_data.async_get_client(call.hass)

    start = __get_date(call.data.get(TibberServiceArgument.START), "start")
    end = __get_date(call.data.get(TibberServiceArgument.END), "end")

    if start >= end:
        end = start + dt.timedelta(days=1)

    tibber_prices: dict[str, Any] = {}
    for tibber_home in tibber_connection.get_homes(only_active=True):
        try:
            intervals = await tibber_home.get_prices(start, end)
        except tibber.PricesNotAvailableError:
            intervals = []
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="get_prices_timeout",
            ) from err
        except tibber.InvalidLoginError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="get_prices_invalid_login",
            ) from err
        except (
            tibber.RetryableHttpExceptionError,
            tibber.FatalHttpExceptionError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="get_prices_communication_failed",
                translation_placeholders={"detail": str(err.status)},
            ) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="get_prices_communication_failed",
                translation_placeholders={"detail": str(err)},
            ) from err

        tibber_prices[tibber_home.name] = [
            {
                "start_time": interval.start.isoformat(),
                "price": interval.consumption.price,
            }
            for interval in intervals
            if interval.consumption is not None
            and interval.consumption.price is not None
        ]

    return {"prices": tibber_prices}


def __get_date(date_input: str | None, mode: str | None) -> datetime:
    """Get date."""
    if not date_input:
        if mode == "end":
            increment = dt.timedelta(days=1)
        else:
            increment = dt.timedelta()
        return dt_util.start_of_local_day() + increment

    if value := dt_util.parse_datetime(date_input):
        return dt_util.as_local(value)

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Tibber integration."""

    hass.services.async_register(
        DOMAIN,
        TibberService.GET_PRICES,
        __get_prices,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
