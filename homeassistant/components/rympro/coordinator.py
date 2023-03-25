"""The Read Your Meter Pro integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence, Set
from datetime import timedelta
import logging
from typing import Any

from pyrympro import CannotConnectError, OperationError, RymPro, UnauthorizedError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MeterSensor

SCAN_INTERVAL = 60 * 60

_LOGGER = logging.getLogger(__name__)


class RymProDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Class to manage fetching RYM Pro data."""

    def __init__(self, hass: HomeAssistant, rympro: RymPro) -> None:
        """Initialize global RymPro data updater."""
        self.rympro = rympro
        interval = timedelta(seconds=SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )
        self._meter_sensors: dict[int, set[MeterSensor]] = {}
        self._first_run = True

    def add_meter_sensor(
        self, meter_id: int, sensor: MeterSensor
    ) -> Callable[[], None]:
        """Add a meter sensor to be fetched."""
        self._meter_sensors.setdefault(meter_id, set())
        self._meter_sensors[meter_id].add(sensor)

        def _remove():
            self._meter_sensors[meter_id].remove(sensor)

        return _remove

    def _sensors_to_get(self, meter_id: int) -> Set[MeterSensor]:
        if self._first_run:
            # get all sensors on first run because we don't yet know which entities are enabled
            sensors = set(MeterSensor)
        else:
            # only get the sensors for enabled entities
            sensors = self._meter_sensors.get(meter_id, set())

        sensors.discard(MeterSensor.TOTAL_CONSUMPTION)
        return sensors

    async def _get_value_for_meter_sensor(
        self, meter_id: int, sensor: MeterSensor
    ) -> Any:
        return await getattr(self.rympro, sensor.value)(meter_id)

    async def _get_values_for_meter(self, meter_id: int) -> dict[MeterSensor, Any]:
        sensors = self._sensors_to_get(meter_id)
        values = await asyncio.gather(
            *(self._get_value_for_meter_sensor(meter_id, sensor) for sensor in sensors)
        )
        return dict(zip(sensors, values))

    async def _get_values_for_meters(
        self, meters: dict[int, Any]
    ) -> Sequence[dict[MeterSensor, Any]]:
        return await asyncio.gather(
            *(self._get_values_for_meter(meter_id) for meter_id in meters)
        )

    def _process_results(
        self, meters: dict[int, Any], results: Sequence[dict[MeterSensor, Any]]
    ):
        return {
            meter_id: {
                MeterSensor.TOTAL_CONSUMPTION: meters[meter_id]["read"],
                **sensors,
            }
            for meter_id, sensors in zip(meters.keys(), results)
        }

    async def _async_update_data(self) -> dict[int, dict[MeterSensor, Any]]:
        """Fetch data from Rym Pro."""
        try:
            meters = await self.rympro.last_read()
            results = await self._get_values_for_meters(meters)
            self._first_run = False
            return self._process_results(meters, results)
        except UnauthorizedError as error:
            assert self.config_entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            raise UpdateFailed(error) from error
        except (CannotConnectError, OperationError) as error:
            raise UpdateFailed(error) from error
