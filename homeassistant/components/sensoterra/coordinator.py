"""Polling coordinator for the Sensoterra integration."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SCAN_INTERVAL_MINUTES, SENSOR_EXPIRATION_DAYS
from .models import ProbeSensorType, SensoterraSensor


class SensoterraCoordinator(DataUpdateCoordinator[dict[str, SensoterraSensor]]):
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

        # Expire sensors without an update within the last few days
        expiration = datetime.now(UTC) - timedelta(days=SENSOR_EXPIRATION_DAYS)
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
