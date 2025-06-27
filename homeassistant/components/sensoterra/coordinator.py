"""Polling coordinator for the Sensoterra integration."""

from collections.abc import Callable
from datetime import timedelta

from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)
from sensoterra.probe import Probe, Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SCAN_INTERVAL_MINUTES

type SensoterraConfigEntry = ConfigEntry[SensoterraCoordinator]


class SensoterraCoordinator(DataUpdateCoordinator[list[Probe]]):
    """Sensoterra coordinator."""

    config_entry: SensoterraConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: SensoterraConfigEntry, api: CustomerApi
    ) -> None:
        """Initialize Sensoterra coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Sensoterra probe",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.api = api
        self.add_devices_callback: Callable[[list[Probe]], None] | None = None

    async def _async_update_data(self) -> list[Probe]:
        """Fetch data from Sensoterra Customer API endpoint."""
        try:
            probes = await self.api.poll()
        except ApiAuthError as err:
            raise ConfigEntryError(err) from err
        except ApiTimeout as err:
            raise UpdateFailed("Timeout communicating with Sensotera API") from err

        if self.add_devices_callback is not None:
            self.add_devices_callback(probes)

        return probes

    def get_sensor(self, id: str | None) -> Sensor | None:
        """Try to find the sensor in the API result."""
        for probe in self.data:
            for sensor in probe.sensors():
                if sensor.id == id:
                    return sensor
        return None
