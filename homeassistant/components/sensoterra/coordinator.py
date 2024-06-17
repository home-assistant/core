"""Polling coordinator for the Sensoterra integration."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging

from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL
from .models import ProbeSensorType, SensoterraSensor

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SensoterraCoordinator(DataUpdateCoordinator[dict[str, SensoterraSensor]]):
    """Sensoterra coordinator."""

    def __init__(self, hass: HomeAssistant, api: CustomerApi) -> None:
        """Initialize Sensoterra coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Sensoterra probe",
            # Polling interval. Will only be polled if there are subscribers (sensors).
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api = api
        self.add_devices_callback: (
            Callable[[dict[str, SensoterraSensor]], None] | None
        ) = None

    async def _async_update_data(self) -> dict[str, SensoterraSensor]:
        """Fetch data from Sensoterra Customer API endpoint."""
        current_sensors = set(self.async_contexts())
        try:
            probes = await self.api.poll()
        except ApiAuthError as err:
            raise ConfigEntryError(err) from err
        except ApiTimeout as err:
            raise UpdateFailed("Timeout communicating with Sensotera API") from err
        else:
            # API returns a probe/sensor data structure which needs to be flattened.
            sensors: list[SensoterraSensor] = []
            for probe in probes:
                if probe.battery is not None:
                    sensors.append(SensoterraSensor(probe, ProbeSensorType.BATTERY))
                if probe.rssi is not None:
                    sensors.append(SensoterraSensor(probe, ProbeSensorType.RSSI))
                # Add soil moistere and temperature sensors at various depths.
                sensors.extend(
                    [
                        SensoterraSensor(probe, sensor)
                        for sensor in probe.sensors()
                        if sensor.depth is not None
                        and sensor.type.lower() in iter(ProbeSensorType)
                    ]
                )
                sensors.append(SensoterraSensor(probe, ProbeSensorType.LASTSEEN))

            # Only consider readings updated after the last poll
            expiration = datetime.now(UTC) - timedelta(seconds=SCAN_INTERVAL)
            for sensor in sensors:
                if sensor.timestamp is None or sensor.timestamp < expiration:
                    sensor.value = None

            # Add new devices
            if self.add_devices_callback is not None:
                self.add_devices_callback(
                    {
                        sensor.id: sensor
                        for sensor in sensors
                        if sensor.id not in current_sensors
                    }
                )

        return {sensor.id: sensor for sensor in sensors}
