"""Provides the Aircon class for controlling an AirTouch air conditioner."""

import logging

from .airtouch_sensor import Sensor
from .airtouch_zone import AirtouchZone
from .enums import AcMode

_LOGGER = logging.getLogger(__name__)


class Aircon:
    """Represents an AirTouch air conditioner object."""

    def __init__(self, ac_id: int) -> None:
        """Initialize the Aircon with the given AC identifier."""
        self.ac_id = ac_id
        self._zones: list[AirtouchZone] = []
        self._sensors: list[Sensor] = []
        self._status: bool = False
        self._fan_speed: int = 0
        self._room_temperature: float = 0
        self._desired_temperature: int = 0
        self._mode: AcMode = AcMode.AUTO
        self._brand_id: int = 0
        self._system_id: str = ""
        self.groups: list[dict[str, int | str]] = []
        self.group_temperatures: dict[int, int] = {}
        self.group_target_temperatures: dict[int, int] = {}
        self.group_power_states: dict[int, bool] = {}

    @property
    def zones(self) -> list[AirtouchZone]:
        """Return the list of zones controlled by this AC."""
        return self._zones

    @zones.setter
    def zones(self, new_zones: list[AirtouchZone]) -> None:
        """Set the list of zones for this AC."""
        self._zones = new_zones

    @property
    def sensors(self) -> list[Sensor]:
        """Return the list of sensors associated with this AC."""
        return self._sensors

    @sensors.setter
    def sensors(self, new_sensors: list[Sensor]) -> None:
        """Set the list of sensors for this AC."""
        self._sensors = new_sensors

    @property
    def status(self) -> bool:
        """Return whether the AC unit is currently on (True) or off (False)."""
        return self._status

    @status.setter
    def status(self, is_on: bool) -> None:
        """Set the AC unit status."""
        self._status = is_on

    @property
    def fan_speed(self) -> int:
        """Return the current fan speed setting."""
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, speed: int) -> None:
        """Set the fan speed of the AC."""
        self._fan_speed = speed

    @property
    def room_temperature(self) -> float:
        """Return the current room temperature as reported by the AC."""
        return self._room_temperature

    @room_temperature.setter
    def room_temperature(self, temperature: float) -> None:
        """Set the current room temperature for this AC."""
        self._room_temperature = temperature

    @property
    def desired_temperature(self) -> int:
        """Return the desired (target) temperature set on the AC."""
        return self._desired_temperature

    @desired_temperature.setter
    def desired_temperature(self, temperature: int) -> None:
        """Set the desired (target) temperature for this AC."""
        self._desired_temperature = temperature

    @property
    def mode(self) -> AcMode:
        """Return the current AC operating mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: AcMode) -> None:
        """Set the AC operating mode."""
        self._mode = new_mode

    @property
    def brand_id(self) -> int:
        """Return the brand identifier for this AC."""
        return self._brand_id

    @brand_id.setter
    def brand_id(self, new_brand_id: int) -> None:
        """Set the brand identifier for this AC."""
        self._brand_id = new_brand_id

    @property
    def system_id(self) -> str:
        """Return the AirTouch controller system identifier."""
        return self._system_id

    @system_id.setter
    def system_id(self, new_system_id: str) -> None:
        """Set the AirTouch controller system identifier."""
        self._system_id = new_system_id
