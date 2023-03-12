"""The Read Your Meter Pro integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
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

    async def _sensor_call(self, meter_id: int, sensor: MeterSensor) -> Any:
        return await getattr(self.rympro, sensor.value)(meter_id)

    async def _results_for_meter(self, meter_id: int) -> dict[MeterSensor, Any]:
        if self._first_run:
            sensors = set(MeterSensor)
        else:
            sensors = self._meter_sensors.get(meter_id, set())
        sensors.discard(MeterSensor.TOTAL_CONSUMPTION)
        values = await asyncio.gather(
            *(self._sensor_call(meter_id, sensor) for sensor in sensors)
        )
        return dict(zip(sensors, values))

    async def _async_update_data(self) -> dict[int, dict[MeterSensor, Any]]:
        """Fetch data from Rym Pro."""
        try:
            meters = await self.rympro.last_read()
            raw = await asyncio.gather(
                *(self._results_for_meter(meter_id) for meter_id in meters)
            )
            self._first_run = False
            return {
                meter_id: {
                    MeterSensor.TOTAL_CONSUMPTION: meters[meter_id]["read"],
                    **sensors,
                }
                for meter_id, sensors in zip(meters.keys(), raw)
            }
        except UnauthorizedError as error:
            assert self.config_entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            raise UpdateFailed(error) from error
        except (CannotConnectError, OperationError) as error:
            raise UpdateFailed(error) from error
