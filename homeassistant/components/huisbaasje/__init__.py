"""The Huisbaasje integration."""
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from energyflip import EnergyFlip, EnergyFlipException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    FETCH_TIMEOUT,
    POLLING_INTERVAL,
    SENSOR_TYPE_RATE,
    SENSOR_TYPE_THIS_DAY,
    SENSOR_TYPE_THIS_MONTH,
    SENSOR_TYPE_THIS_WEEK,
    SENSOR_TYPE_THIS_YEAR,
    SOURCE_TYPES,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huisbaasje from a config entry."""
    # Create the Huisbaasje client
    energyflip = EnergyFlip(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        source_types=SOURCE_TYPES,
        request_timeout=FETCH_TIMEOUT,
    )

    # Attempt authentication. If this fails, an exception is thrown
    try:
        await energyflip.authenticate()
    except EnergyFlipException as exception:
        _LOGGER.error("Authentication failed: %s", str(exception))
        return False

    async def async_update_data() -> dict[str, dict[str, Any]]:
        return await async_update_huisbaasje(energyflip)

    # Create a coordinator for polling updates
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=POLLING_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    # Load the client in the data of home assistant
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    # Offload the loading of entities to the platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Forward the unloading of the entry to the platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If successful, unload the Huisbaasje client
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_huisbaasje(energyflip: EnergyFlip) -> dict[str, dict[str, Any]]:
    """Update the data by performing a request to Huisbaasje."""
    try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(FETCH_TIMEOUT):
            if not energyflip.is_authenticated():
                _LOGGER.warning("Huisbaasje is unauthenticated. Reauthenticating")
                await energyflip.authenticate()

            current_measurements = await energyflip.current_measurements()

            return {
                source_type: {
                    SENSOR_TYPE_RATE: _get_measurement_rate(
                        current_measurements, source_type
                    ),
                    SENSOR_TYPE_THIS_DAY: _get_cumulative_value(
                        current_measurements, source_type, SENSOR_TYPE_THIS_DAY
                    ),
                    SENSOR_TYPE_THIS_WEEK: _get_cumulative_value(
                        current_measurements, source_type, SENSOR_TYPE_THIS_WEEK
                    ),
                    SENSOR_TYPE_THIS_MONTH: _get_cumulative_value(
                        current_measurements, source_type, SENSOR_TYPE_THIS_MONTH
                    ),
                    SENSOR_TYPE_THIS_YEAR: _get_cumulative_value(
                        current_measurements, source_type, SENSOR_TYPE_THIS_YEAR
                    ),
                }
                for source_type in SOURCE_TYPES
            }
    except EnergyFlipException as exception:
        raise UpdateFailed(f"Error communicating with API: {exception}") from exception


def _get_cumulative_value(
    current_measurements: dict,
    source_type: str,
    period_type: str,
):
    """Get the cumulative energy consumption for a certain period.

    :param current_measurements: The result from the Huisbaasje client
    :param source_type: The source of energy (electricity or gas)
    :param period_type: The period for which cumulative value should be given.
    """
    if source_type in current_measurements:
        if (
            period_type in current_measurements[source_type]
            and current_measurements[source_type][period_type] is not None
        ):
            return current_measurements[source_type][period_type]["value"]
    else:
        _LOGGER.error(
            "Source type %s not present in %s", source_type, current_measurements
        )
    return None


def _get_measurement_rate(current_measurements: dict, source_type: str):
    if source_type in current_measurements:
        if (
            "measurement" in current_measurements[source_type]
            and current_measurements[source_type]["measurement"] is not None
        ):
            return current_measurements[source_type]["measurement"]["rate"]
    else:
        _LOGGER.error(
            "Source type %s not present in %s", source_type, current_measurements
        )
    return None
