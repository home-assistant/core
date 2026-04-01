"""Data update coordinator for Subaru."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from subarulink import Controller as SubaruAPI, SubaruException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_UPDATE_ENABLED,
    COORDINATOR_NAME,
    FETCH_INTERVAL,
    VEHICLE_LAST_UPDATE,
    VEHICLE_VIN,
)

_LOGGER = logging.getLogger(__name__)


class SubaruDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Subaru data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        *,
        controller: SubaruAPI,
        vehicle_info: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=COORDINATOR_NAME,
            update_interval=timedelta(seconds=FETCH_INTERVAL),
        )
        self._controller = controller
        self._vehicle_info = vehicle_info

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Subaru API."""
        try:
            return await _refresh_subaru_data(
                self.config_entry, self._vehicle_info, self._controller
            )
        except SubaruException as err:
            raise UpdateFailed(err.message) from err


async def _refresh_subaru_data(
    config_entry: ConfigEntry,
    vehicle_info: dict[str, dict[str, Any]],
    controller: SubaruAPI,
) -> dict[str, Any]:
    """Refresh local data with data fetched via Subaru API.

    Subaru API calls assume a server side vehicle context
    Data fetch/update must be done for each vehicle
    """
    data: dict[str, Any] = {}

    for vehicle in vehicle_info.values():
        vin = vehicle[VEHICLE_VIN]

        # Optionally send an "update" remote command to vehicle (throttled with update_interval)
        if config_entry.options.get(CONF_UPDATE_ENABLED, False):
            await _update_subaru(vehicle, controller)

        # Fetch data from Subaru servers
        await controller.fetch(vin, force=True)

        # Update our local data that will go to entity states
        if received_data := await controller.get_data(vin):
            data[vin] = received_data

    return data


async def _update_subaru(vehicle: dict[str, Any], controller: SubaruAPI) -> None:
    """Commands remote vehicle update (polls the vehicle to update subaru API cache)."""
    cur_time = time.time()
    last_update = vehicle[VEHICLE_LAST_UPDATE]

    if cur_time - last_update > controller.get_update_interval():
        await controller.update(vehicle[VEHICLE_VIN], force=True)
        vehicle[VEHICLE_LAST_UPDATE] = cur_time
