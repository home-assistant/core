"""Green Planet Energy integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta

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

# Time range options
TIME_RANGE_DAY = "day"
TIME_RANGE_NIGHT = "night"
TIME_RANGE_FULL_DAY = "full_day"

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

        # Get coordinator data
        data = coordinator.data
        api = coordinator.api

        # Get current hour to filter out past results
        now = dt_util.now()
        current_hour = now.hour

        # Calculate cheapest duration based on time range
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

        # Create ISO timestamp for start time
        # Determine if we should use today or tomorrow's date
        start_time = dt_util.start_of_local_day(now).replace(
            hour=start_hour_result, minute=0, second=0, microsecond=0
        )

        # Check if the calculated time is in the past
        # If so, it must be tomorrow (happens for night hours 0-5 or day hours when outside day period)
        if start_time < now:
            start_time = start_time + timedelta(days=1)

        # Calculate hours until start
        hours_until_start = (start_time - now).total_seconds() / 3600

        return {
            "duration": duration,
            "average_price": round(avg_price / 100, 4),
            "start_time": start_time.isoformat(),
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
