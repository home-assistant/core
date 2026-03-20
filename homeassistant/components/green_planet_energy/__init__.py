"""Green Planet Energy integration for Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GreenPlanetEnergyUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type GreenPlanetEnergyConfigEntry = ConfigEntry[GreenPlanetEnergyUpdateCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service constants
SERVICE_GET_CHEAPEST_DURATION = "get_cheapest_duration"
ATTR_DURATION = "duration"
ATTR_TIME_RANGE = "time_range"
ATTR_MODE = "mode"

# Time range options
TIME_RANGE_DAY = "day"
TIME_RANGE_NIGHT = "night"
TIME_RANGE_FULL_DAY = "full_day"

# Mode options
MODE_CHEAPEST_WINDOW = "cheapest_window"
MODE_PRICE_SCHEDULE = "price_schedule"

SERVICE_GET_CHEAPEST_DURATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=24)
        ),
        vol.Optional(ATTR_TIME_RANGE, default=TIME_RANGE_FULL_DAY): vol.In(
            [TIME_RANGE_DAY, TIME_RANGE_NIGHT, TIME_RANGE_FULL_DAY]
        ),
        vol.Optional(ATTR_MODE, default=MODE_CHEAPEST_WINDOW): vol.In(
            [MODE_CHEAPEST_WINDOW, MODE_PRICE_SCHEDULE]
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Green Planet Energy component."""

    async def get_cheapest_duration(call: ServiceCall) -> ServiceResponse:
        """Handle the get_cheapest_duration service call."""
        # This integration has single_config_entry, so get the first entry
        entries = hass.config_entries.async_entries(DOMAIN)

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

        coordinator: GreenPlanetEnergyUpdateCoordinator = entry.runtime_data

        duration = call.data[ATTR_DURATION]
        time_range = call.data[ATTR_TIME_RANGE]
        mode = call.data[ATTR_MODE]
        data = coordinator.data
        api = coordinator.api
        now = dt_util.now()
        current_hour = now.hour

        result: tuple[float | None, int | None]

        if time_range == TIME_RANGE_DAY:
            result = api.get_cheapest_duration_day(data, duration, current_hour)
        elif time_range == TIME_RANGE_NIGHT:
            result = api.get_cheapest_duration_night(data, duration, current_hour)
        else:  # TIME_RANGE_FULL_DAY
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

        # If the calculated start time is in the past, shift to tomorrow
        if start_time < now:
            start_time = start_time + timedelta(days=1)

        end_time = start_time + timedelta(hours=duration)

        if mode == MODE_PRICE_SCHEDULE:
            return _build_window_price_schedule(
                data, time_range, start_hour_result, duration, start_time, end_time, now
            )

        # MODE_CHEAPEST_WINDOW: return summary with average price and timing
        hours_until_start = (start_time - now).total_seconds() / 3600

        return {
            "duration": duration,
            "average_price": round(avg_price / 100, 4),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "hours_until_start": round(hours_until_start, 1),
            "time_range": time_range,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CHEAPEST_DURATION,
        get_cheapest_duration,
        schema=SERVICE_GET_CHEAPEST_DURATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


def _build_window_price_schedule(
    data: dict[str, float],
    time_range: str,
    start_hour: int,
    duration: float,
    start_time: datetime,
    end_time: datetime,
    now: datetime,
) -> dict:
    """Build per-15-minute-slot prices for the cheapest window found by the API.

    Iterates every 15-minute slot within [start_time, start_time + duration]
    and looks up keys of the form ``gpe_price_HH_MM[_tomorrow]``.  15-minute
    resolution is required by law, so every slot is expected to be present.
    """
    today_start = dt_util.start_of_local_day(now)
    tomorrow_start = today_start + timedelta(days=1)
    current_hour = now.hour

    # Mirror the use_tomorrow logic from the API client.
    use_tomorrow = time_range == TIME_RANGE_NIGHT or (
        time_range == TIME_RANGE_DAY and (current_hour < 6 or current_hour >= 18)
    )

    # Walk in 15-minute steps for the full requested duration.
    total_minutes = int(duration * 60)
    step_minutes = 15
    prices = []

    for offset_minutes in range(0, total_minutes, step_minutes):
        slot_start = start_time + timedelta(minutes=offset_minutes)
        slot_end = slot_start + timedelta(minutes=step_minutes)
        hour = slot_start.hour
        minute = slot_start.minute

        # Determine whether this slot's data lives in today's or tomorrow's keys.
        if use_tomorrow:
            if hour < 6:
                suffix = "_tomorrow"
                day_start = tomorrow_start
            elif hour >= 18:
                suffix = ""
                day_start = today_start
            else:
                suffix = "_tomorrow"
                day_start = tomorrow_start
        else:
            suffix = ""
            day_start = today_start

        quarter_key = f"gpe_price_{hour:02d}_{minute:02d}{suffix}"
        price_value = data.get(quarter_key)

        if price_value is None:
            continue

        # Reconstruct slot_start from day_start to guarantee correct date.
        slot_start = day_start.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        slot_end = slot_start + timedelta(minutes=step_minutes)

        prices.append(
            {
                "start_time": slot_start.isoformat(),
                "end_time": slot_end.isoformat(),
                "price": round(price_value / 100, 4),
            }
        )

    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "time_range": time_range,
        "prices": prices,
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: GreenPlanetEnergyConfigEntry
) -> bool:
    """Set up Green Planet Energy from a config entry."""
    coordinator = GreenPlanetEnergyUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GreenPlanetEnergyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
