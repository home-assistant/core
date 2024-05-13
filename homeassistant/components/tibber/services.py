"""Services for Tibber integration."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from functools import partial
from typing import Final

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .sensor import TibberDataCoordinator

PRICE_SERVICE_NAME = "get_prices"
ATTR_START: Final = "start"
ATTR_END: Final = "end"

SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
    }
)


async def __get_prices(call: ServiceCall, *, hass: HomeAssistant) -> ServiceResponse:
    tibber_connection = hass.data[DOMAIN]
    coordinator = TibberDataCoordinator(hass, tibber_connection)

    for home in tibber_connection.get_homes(only_active=False):
        tibber_home = home

    start = __get_date(call.data.get(ATTR_START), "start")
    end = __get_date(call.data.get(ATTR_END), "end")

    if start >= end:
        end = start + dt.timedelta(days=1)

    data = await coordinator.get_prices(tibber_home)

    selected_data = [
        price
        for price in data
        if price["start_time"].replace(tzinfo=None) >= start
        and price["start_time"].replace(tzinfo=None) < end
    ]

    return {"prices": selected_data}


def __get_date(date_input: str | None, mode: str | None) -> date | datetime:
    """Get date."""
    if not date_input:
        if mode == "end":
            return datetime.fromisoformat(
                dt_util.now().date().isoformat()
            ) + dt.timedelta(days=1)
        return datetime.fromisoformat(dt_util.now().date().isoformat())

    if value := dt_util.parse_datetime(date_input):
        return value

    raise ServiceValidationError(
        "Invalid datetime provided.",
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
        PRICE_SERVICE_NAME,
        partial(__get_prices, hass=hass),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
