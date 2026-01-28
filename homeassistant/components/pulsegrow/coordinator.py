"""DataUpdateCoordinator for PulseGrow integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from aiopulsegrow import Device, Hub, PulsegrowClient, PulsegrowError, Sensor

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import PulseGrowConfigEntry


@dataclass
class PulseGrowData:
    """Data class to hold PulseGrow API data."""

    devices: dict[str, Device]
    hubs: dict[str, Hub]
    sensors: dict[str, Sensor]


class PulseGrowDataUpdateCoordinator(DataUpdateCoordinator[PulseGrowData]):
    """Class to manage fetching PulseGrow data from the API."""

    config_entry: PulseGrowConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: PulsegrowClient,
        config_entry: PulseGrowConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> PulseGrowData:
        """Fetch data from PulseGrow API."""
        try:
            return await self._fetch_all_data()
        except PulsegrowError as err:
            raise UpdateFailed(
                f"Error communicating with PulseGrow API: {err}"
            ) from err

    async def _fetch_all_data(self) -> PulseGrowData:
        """Fetch all data from the API."""
        # Fetch all devices (includes most_recent_data_point)
        device_data = await self.client.get_all_devices()

        devices: dict[str, Device] = {}
        hubs: dict[str, Hub] = {}
        sensors: dict[str, Sensor] = {}

        # Process devices from DeviceData
        for device in device_data.devices:
            # Use guid as primary identifier, fall back to id
            device_id = str(device.guid or device.id)
            devices[device_id] = device

        # Process sensors from DeviceData
        for sensor in device_data.sensors:
            sensor_id = str(sensor.id)
            sensors[sensor_id] = sensor

        # Fetch hub IDs from API
        hub_ids_to_fetch: set[int] = set()
        try:
            api_hub_ids = await self.client.get_hub_ids()
            hub_ids_to_fetch.update(api_hub_ids)
        except PulsegrowError:
            LOGGER.debug("Could not fetch hub IDs from API")

        # Fetch hub details in parallel
        if hub_ids_to_fetch:
            hub_tasks = [
                self.client.get_hub_details(hub_id) for hub_id in hub_ids_to_fetch
            ]
            hub_results = await asyncio.gather(*hub_tasks, return_exceptions=True)

            for hub_id, result in zip(hub_ids_to_fetch, hub_results, strict=False):
                if isinstance(result, BaseException):
                    LOGGER.debug("Could not fetch hub details for hub_id %s", hub_id)
                elif result is not None:
                    hub_id_str = str(hub_id)
                    hubs[hub_id_str] = result

        return PulseGrowData(
            devices=devices,
            hubs=hubs,
            sensors=sensors,
        )
