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
    """Model Sensoterra probe data produced by the API.

    A Sensoterra probe contains multiple sensors. Home Assistant prefers
    to have a single list of sensors.
    """

    def __init__(
        self,
        expiration: datetime,
        probe: Probe,
        type: str,
        sensor: Sensor | None = None,
    ) -> None:
        """Initialise SensoterraSensor."""
        self.name = probe.name
        self.sku = probe.sku
        self.serial = probe.serial
        self.location = probe.location
        self.type = type
        self.depth = None
        self.soil = None
        if sensor is not None:
            self.depth = sensor.depth
            self.soil = sensor.soil
            self.value = round(sensor.value, 1)
            self.timestamp = sensor.timestamp
        elif type == "BATTERY":
            if probe.battery == "NORMAL":
                self.value = 100
            elif probe.battery == "FAIR":
                self.value = 50
            elif probe.battery == "POOR":
                self.value = 10
            else:
                self.value = None
            if self.value is not None:
                self.timestamp = probe.timestamp
        elif type == "LASTSEEN":
            self.value = probe.timestamp
            self.timestamp = datetime.now(UTC)
        elif type == "RSSI":
            if probe.rssi is not None:
                self.value = round(probe.rssi, 0)
                self.timestamp = probe.timestamp
        else:
            raise UpdateFailed(f"Unknown sensor type {type}")
        if self.timestamp is None or self.timestamp < expiration:
            self.value = None


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
            # Polling interval. Will only be polled if there are subscribers.
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
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed(err) from err
        except ApiTimeout as err:
            raise UpdateFailed("Timeout communicating with Sensotera API") from err
        else:
            sensors = {}
            expiration = datetime.now(UTC) - timedelta(seconds=SCAN_INTERVAL)
            for probe in probes:
                for sensor in probe.sensors():
                    if sensor.type == "MOISTURE" and sensor.unit == "SI":
                        sensor_id = f"{sensor.id}-SI"
                        sensor_type = "SI"
                    else:
                        sensor_id = sensor.id
                        sensor_type = sensor.type
                    sensors[sensor_id] = SensoterraSensor(
                        expiration, probe, sensor_type, sensor
                    )
                if probe.battery is not None:
                    sensor_id = f"{probe.serial}-BATTERY"
                    sensors[sensor_id] = SensoterraSensor(expiration, probe, "BATTERY")
                if probe.rssi is not None:
                    sensor_id = f"{probe.serial}-RSSI"
                    sensors[sensor_id] = SensoterraSensor(expiration, probe, "RSSI")
                sensor_id = f"{probe.serial}-LASTSEEN"
                sensors[sensor_id] = SensoterraSensor(expiration, probe, "LASTSEEN")

            if self.add_devices_callback is not None:
                # Add new devices
                self.add_devices_callback(
                    {
                        sensor_id: sensor
                        for (sensor_id, sensor) in sensors.items()
                        if sensor_id not in current_sensors
                    }
                )

        return sensors
