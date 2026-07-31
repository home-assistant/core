"""Services for Green Planet Energy integration."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.service import async_get_config_entry
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DOMAIN

SERVICE_GET_PRICES = "get_prices"
ATTR_HOURS = "hours"
SERVICE_GET_CHEAPEST_DURATION = "get_cheapest_duration"

ATTR_DURATION = "duration"
ATTR_TIME_RANGE = "time_range"

TIME_RANGE_DAY = "day"
TIME_RANGE_NIGHT = "night"
TIME_RANGE_FULL_DAY = "full_day"


def _validate_hours(v: float) -> float:
    """Validate that hours is a multiple of 0.25 (15 minutes)."""
    if abs(v * 4 - round(v * 4)) >= 1e-9:
        raise vol.Invalid("hours must be a multiple of 0.25 (15 minutes)")
    return v


SERVICE_GET_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Required(ATTR_HOURS): vol.All(
            vol.Coerce(float),
            vol.Range(min=0.25, max=24),
            _validate_hours,
        ),
    }
)

SERVICE_GET_CHEAPEST_DURATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=24)
        ),
        vol.Optional(ATTR_TIME_RANGE, default=TIME_RANGE_FULL_DAY): vol.In(
            [TIME_RANGE_DAY, TIME_RANGE_NIGHT, TIME_RANGE_FULL_DAY]
        ),
    }
)


async def get_cheapest_duration(call: ServiceCall) -> ServiceResponse:
    """Find the cheapest consecutive time window for a given duration."""
    entries = call.hass.config_entries.async_entries(DOMAIN)

    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry",
        )

    entry = entries[0]

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    coordinator = entry.runtime_data
    duration = call.data[ATTR_DURATION]
    time_range = call.data[ATTR_TIME_RANGE]
    data = coordinator.data
    api = coordinator.api
    now = dt_util.now()
    current_hour = now.hour

    result: tuple[float | None, int | None]

    if time_range == TIME_RANGE_DAY:
        result = api.get_cheapest_duration_day(data, duration, current_hour)
    elif time_range == TIME_RANGE_NIGHT:
        result = api.get_cheapest_duration_night(data, duration, current_hour)
    else:
        result = api.get_cheapest_duration(data, duration, current_hour)

    avg_price, start_hour_result = result

    if avg_price is None or start_hour_result is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_data_available",
        )

    start_time = dt_util.start_of_local_day(now).replace(
        hour=start_hour_result, minute=0, second=0, microsecond=0
    )
    if start_time < now:
        start_time = start_time + timedelta(days=1)

    end_time = start_time + timedelta(hours=duration)
    hours_until_start = (start_time - now).total_seconds() / 3600

    return {
        "duration": duration,
        "average_price": round(avg_price / 100, 4),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "hours_until_start": round(hours_until_start, 1),
        "time_range": time_range,
    }


async def get_prices(call: ServiceCall) -> ServiceResponse:
    """Return raw 15-minute-slot electricity prices for the next N hours.

    Prices are in EUR/kWh. Slots for which the API has no data yet (e.g.
    tomorrow's prices have not been published yet) are silently omitted
    from the result.
    """
    entry = async_get_config_entry(call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID])
    data = entry.runtime_data.data
    hours: float = call.data[ATTR_HOURS]

    now = dt_util.now()
    slot_timestamp = int(dt_util.as_timestamp(now) // 900 * 900)
    slot_start = dt_util.as_local(dt_util.utc_from_timestamp(slot_timestamp))
    end_time = slot_start + timedelta(hours=hours)
    today = slot_start.date()
    tomorrow = today + timedelta(days=1)

    slots: list[JsonValueType] = []
    current = slot_start
    while current < end_time:
        slot_end = current + timedelta(minutes=15)
        h = current.hour
        m = current.minute
        current_date = current.date()

        if current_date == today:
            key = f"gpe_price_{h:02d}_{m:02d}"
        elif current_date == tomorrow:
            key = f"gpe_price_{h:02d}_{m:02d}_tomorrow"
        else:
            current = slot_end
            continue

        if key in data:
            slots.append(
                {
                    "start": current.isoformat(),
                    "end": slot_end.isoformat(),
                    "price": round(data[key] / 100, 6),
                }
            )

        current = slot_end

    return {
        "prices": slots,
        "hours_requested": hours,
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Green Planet Energy."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CHEAPEST_DURATION,
        get_cheapest_duration,
        schema=SERVICE_GET_CHEAPEST_DURATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICES,
        get_prices,
        schema=SERVICE_GET_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
