"""The Huisbaasje integration."""
from datetime import timedelta
import logging

import async_timeout
from huisbaasje import Huisbaasje, HuisbaasjeException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
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

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Huisbaasje component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Huisbaasje from a config entry."""
    # Create the Huisbaasje client
    huisbaasje = Huisbaasje(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        source_types=SOURCE_TYPES,
        request_timeout=FETCH_TIMEOUT,
    )

    # Attempt authentication. If this fails, an exception is thrown
    try:
        await huisbaasje.authenticate()
    except HuisbaasjeException as exception:
        _LOGGER.error("Authentication failed: %s", str(exception))
        return False

    async def async_update_data():
        return await async_update_huisbaasje(huisbaasje)

    # Create a coordinator for polling updates
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=POLLING_INTERVAL),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    # Load the client in the data of home assistant
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        DATA_COORDINATOR: coordinator
    }

    # Offload the loading of entities to the platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    # Forward the unloading of the entry to the platform
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "sensor"
    )

    # If successful, unload the Huisbaasje client
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def async_update_huisbaasje(huisbaasje):
    """Update the data by performing a request to Huisbaasje."""
    try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(FETCH_TIMEOUT):
            if not huisbaasje.is_authenticated():
                _LOGGER.warning("Huisbaasje is unauthenticated. Reauthenticating...")
                await huisbaasje.authenticate()

            current_measurements = await huisbaasje.current_measurements()

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
    except HuisbaasjeException as exception:
        raise UpdateFailed(f"Error communicating with API: {exception}") from exception


def _get_cumulative_value(
    current_measurements: dict,
    source_type: str,
    period_type: str,
):
    """
    Get the cumulative energy consumption for a certain period.

    :param current_measurements: The result from the Huisbaasje client
    :param source_type: The source of energy (electricity or gas)
    :param period_type: The period for which cumulative value should be given.
    """
    if source_type in current_measurements.keys():
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
