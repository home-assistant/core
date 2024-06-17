"""Sensoterra models."""

from datetime import UTC, datetime
from enum import IntEnum, StrEnum, auto

from sensoterra.probe import Probe, Sensor

from homeassistant.helpers.update_coordinator import UpdateFailed


class ProbeSensorType(StrEnum):
    """Generic sensors within a Sensoterra probe."""

    MOISTURE = auto()
    SI = auto()
    TEMPERATURE = auto()
    BATTERY = auto()
    RSSI = auto()
    LASTSEEN = auto()


class ProbeBatteryLevel(IntEnum):
    """Map API strings to corresponding integers."""

    NORMAL = 100
    FAIR = 50
    POOR = 10


class SensoterraSensor:
    """Model Sensoterra probe data produced by the API."""

    depth: int | None = None
    soil: str | None = None
    timestamp: datetime | None = None
    value: float | None = None
    type: ProbeSensorType

    def __init__(
        self,
        probe: Probe,
        sensor: Sensor | ProbeSensorType,
    ) -> None:
        """Initialise Sensoterra sensor."""
        self.name = probe.name
        self.sku = probe.sku
        self.serial = probe.serial
        self.location = probe.location
        if isinstance(sensor, Sensor):
            self.id = sensor.id
            self.type = ProbeSensorType[sensor.type]
            self.depth = sensor.depth
            self.soil = sensor.soil
            self.value = sensor.value
            self.timestamp = sensor.timestamp
        else:
            self.id = f"{probe.serial}-{sensor}"
            self.type = sensor
            if self.type == ProbeSensorType.RSSI:
                if probe.rssi is not None:
                    self.value = probe.rssi
                    self.timestamp = probe.timestamp
            elif self.type == ProbeSensorType.BATTERY:
                try:
                    self.value = ProbeBatteryLevel[probe.battery]
                except KeyError:
                    pass
                else:
                    self.timestamp = probe.timestamp
            elif self.type == ProbeSensorType.LASTSEEN:
                self.value = probe.timestamp
                self.timestamp = datetime.now(UTC)
            else:
                raise UpdateFailed(f"Unknown sensor {sensor}")
