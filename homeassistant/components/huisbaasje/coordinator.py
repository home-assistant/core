"""The EnergyFlip integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from energyflip import EnergyFlip, EnergyFlipException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
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


class EnergyFlipUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """EnergyFlip data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        energyflip: EnergyFlip,
    ) -> None:
        """Initialize the Huisbaasje data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="sensor",
            update_interval=timedelta(seconds=POLLING_INTERVAL),
        )

        self._energyflip = energyflip

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Update the data by performing a request to EnergyFlip."""
        try:
            # Note: TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(FETCH_TIMEOUT):
                if not self._energyflip.is_authenticated():
                    _LOGGER.warning("EnergyFlip is unauthenticated. Reauthenticating")
                    await self._energyflip.authenticate()

                current_measurements = await self._energyflip.current_measurements()

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
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception


def _get_cumulative_value(
    current_measurements: dict,
    source_type: str,
    period_type: str,
):
    """Get the cumulative energy consumption for a certain period.

    :param current_measurements: The result from the EnergyFlip client
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
