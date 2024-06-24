"""Polling coordinator for the Sensoterra integration."""

from collections.abc import Callable
from datetime import timedelta

from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)
from sensoterra.probe import Sensor

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SCAN_INTERVAL_MINUTES
from .models import SensoterraSensor


class SensoterraCoordinator(DataUpdateCoordinator[list[SensoterraSensor]]):
    """Sensoterra coordinator."""

    def __init__(self, hass: HomeAssistant, api: CustomerApi) -> None:
        """Initialize Sensoterra coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Sensoterra probe",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.api = api
        self.add_devices_callback: Callable[[list[SensoterraSensor]], None] | None = (
            None
        )

    async def _async_update_data(self) -> list[SensoterraSensor]:
        """Fetch data from Sensoterra Customer API endpoint."""
        current_sensors = set(self.async_contexts())
        try:
            probes = await self.api.poll()
        except ApiAuthError as err:
            raise ConfigEntryError(err) from err
        except ApiTimeout as err:
            raise UpdateFailed("Timeout communicating with Sensotera API") from err

        if self.add_devices_callback is not None:
            self.add_devices_callback(
                [
                    SensoterraSensor(probe, sensor)
                    for probe in probes
                    for sensor in probe.sensors()
                    if sensor.id not in current_sensors
                ]
            )

        return [
            SensoterraSensor(probe, sensor)
            for probe in probes
            for sensor in probe.sensors()
        ]

    def get_sensor(self, id: str | None) -> Sensor | None:
        """Try to find the sensor in the API result."""
        for _, sensor in self.data:
            if sensor.id == id:
                return sensor
        return None
