"""Polling coordinator for the Sensoterra integration."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging

from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)
from sensoterra.probe import Probe, Sensor

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SensoterraSensor:
    """Model Sensoterra probe data produced by the API."""

    depth: int | None = None
    soil: str | None = None
    timestamp: datetime | None = None
    value: float | None = None

    BATTERY_LEVELS: dict[str, int] = {"NORMAL": 100, "FAIR": 50, "POOR": 10}

    def __init__(
        self,
        probe: Probe,
        sensor: Sensor | str,
    ) -> None:
        """Initialise Sensoterra sensor."""
        self.name = probe.name
        self.sku = probe.sku
        self.serial = probe.serial
        self.location = probe.location
        if isinstance(sensor, Sensor):
            self.id = sensor.id
            self.type = sensor.type
            self.depth = sensor.depth
            self.soil = sensor.soil
            self.value = sensor.value
            self.timestamp = sensor.timestamp
        else:
            self.id = f"{probe.serial}-{sensor}"
            self.type = sensor
            if self.type == "RSSI":
                if probe.rssi is not None:
                    self.value = probe.rssi
                    self.timestamp = probe.timestamp
            elif self.type == "BATTERY":
                if probe.battery in self.BATTERY_LEVELS:
                    self.value = self.BATTERY_LEVELS[probe.battery]
                    self.timestamp = probe.timestamp
            elif self.type == "LASTSEEN":
                self.value = probe.timestamp
                self.timestamp = datetime.now(UTC)
            else:
                raise UpdateFailed(f"Unknown sensor {sensor}")


class SensoterraCoordinator(DataUpdateCoordinator):
    """Sensoterra coordinator."""

    add_devices_callback: Callable[[dict[str, SensoterraSensor]], None] | None

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
        self.add_devices_callback = None

    async def _async_update_data(self) -> dict[str, SensoterraSensor]:
        """Fetch data from Sensoterra Customer API endpoint."""
        try:
            current_sensors = set(self.async_contexts())
            probes = await self.api.poll()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except ApiTimeout as err:
            raise UpdateFailed("Timeout communicating with Sensotera API") from err
        else:
            # Flatten API return probe/sensor data structure.
            sensors: list[SensoterraSensor] = []
            for probe in probes:
                sensors.extend(
                    SensoterraSensor(probe, sensor) for sensor in probe.sensors()
                )
                if probe.battery is not None:
                    sensors.append(SensoterraSensor(probe, "BATTERY"))
                if probe.rssi is not None:
                    sensors.append(SensoterraSensor(probe, "RSSI"))
                sensors.append(SensoterraSensor(probe, "LASTSEEN"))

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
