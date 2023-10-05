"""Constants for the Renson integration."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "renson_healthbox3"
MANUFACTURER = "Renson"
LOGGER: Logger = getLogger(__package__)


class HealthboxRoomBoost:
    """Healthbox  Room Boost object."""

    level: float
    enabled: bool
    remaining: int

    def __init__(
        self, level: float = 100, enabled: bool = False, remaining: int = 900
    ) -> None:
        """Initialize the HB Room Boost."""
        self.level = level
        self.enabled = enabled
        self.remaining = remaining


class HealthboxRoom:
    """Healthbox  Room object."""

    boost: HealthboxRoomBoost

    def __init__(self, room_id: int, room_data: dict[str, Any]) -> None:
        """Initialize the HB Room."""
        self.room_id: int = room_id
        self.name: str = room_data["name"]
        self.type: str = room_data["type"]
        self.sensors_data: list = room_data["sensor"]
        self.room_type: str = room_data["type"]

    @property
    def indoor_temperature(self) -> Decimal:
        """HB Indoor Temperature."""
        return [
            sensor["parameter"]["temperature"]["value"]
            for sensor in self.sensors_data
            if "temperature" in sensor["parameter"]
        ][0]

    @property
    def indoor_humidity(self) -> Decimal:
        """HB Indoor Humidity."""
        return [
            sensor["parameter"]["humidity"]["value"]
            for sensor in self.sensors_data
            if "humidity" in sensor["parameter"]
        ][0]

    @property
    def indoor_co2_concentration(self) -> Decimal | None:
        """HB Indoor CO2 Concentration."""
        co2_concentration = None
        try:
            co2_concentration = [
                sensor["parameter"]["concentration"]["value"]
                for sensor in self.sensors_data
                if "concentration" in sensor["parameter"]
            ][0]
        except IndexError:
            co2_concentration = None
        return co2_concentration

    @property
    def indoor_aqi(self) -> Decimal | None:
        """HB Indoor Air Quality Index."""
        aqi = None
        try:
            aqi = [
                sensor["parameter"]["index"]["value"]
                for sensor in self.sensors_data
                if "index" in sensor["parameter"]
            ][0]
        except IndexError:
            aqi = None
        return aqi


@dataclass
class HealthboxGlobalEntityDescriptionMixin:
    """Mixin values for Healthbox Global entities."""

    value_fn: Callable[[Any], Any]


@dataclass
class HealthboxGlobalSensorEntityDescription(
    SensorEntityDescription, HealthboxGlobalEntityDescriptionMixin
):
    """Class describing Healthbox Global sensor entities."""


@dataclass
class HealthboxRoomEntityDescriptionMixin:
    """Mixin values for Healthbox Room entities."""

    room: HealthboxRoom
    value_fn: Callable[[Any], Any]


@dataclass
class HealthboxRoomSensorEntityDescription(
    SensorEntityDescription, HealthboxRoomEntityDescriptionMixin
):
    """Class describing Healthbox Room sensor entities."""
