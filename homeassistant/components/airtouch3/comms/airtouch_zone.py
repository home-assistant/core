"""Provides the AirtouchZone class for handling a single zone in an AirTouch system."""

from .airtouch_sensor import Sensor
from .enums import ZoneStatus


class AirtouchZone:
    """Represents a single AirTouch zone with temperature and status attributes."""

    def __init__(self, touch_pad_temperature: int) -> None:
        """Initialize the AirtouchZone.

        :param touch_pad_temperature: Initial temperature displayed on the touch pad.
        """
        self._touch_pad_temperature = touch_pad_temperature
        self._sensor = None  # type: Sensor | None
        self._desired_temperature = 0
        self._name = ""
        self._status = ZoneStatus.ZONE_OFF
        self._id = 0

    @property
    def touch_pad_temperature(self) -> int:
        """Return the current touch pad temperature for this zone."""
        return self._touch_pad_temperature

    @touch_pad_temperature.setter
    def touch_pad_temperature(self, value: int) -> None:
        """Set the touch pad temperature.

        :param value: The new touch pad temperature to store.
        """
        self._touch_pad_temperature = value

    @property
    def name(self) -> str:
        """Return the name of this zone."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the name of this zone.

        :param value: The new zone name.
        """
        self._name = value

    @property
    def id(self) -> int:
        """Return the ID of this zone."""
        return self._id

    @id.setter
    def id(self, value: int) -> None:
        """Set the ID for this zone.

        :param value: The new zone ID.
        """
        self._id = value

    @property
    def status(self) -> ZoneStatus:
        """Return the current power/status of this zone."""
        return self._status

    @status.setter
    def status(self, value: ZoneStatus) -> None:
        """Update the power/status of this zone.

        :param value: The new zone status.
        """
        self._status = value

    @property
    def desired_temperature(self) -> int:
        """Return the desired (target) temperature for this zone."""
        return self._desired_temperature

    @desired_temperature.setter
    def desired_temperature(self, value: int) -> None:
        """Set the desired (target) temperature for this zone.

        :param value: The new target temperature.
        """
        self._desired_temperature = value

    @property
    def sensor(self) -> Sensor | None:
        """Return the Sensor object associated with this zone, if any."""
        return self._sensor

    @sensor.setter
    def sensor(self, sensor: Sensor) -> None:
        """Assign a Sensor object to this zone.

        :param sensor: The Sensor instance that measures this zone's temperature.
        """
        self._sensor = sensor
