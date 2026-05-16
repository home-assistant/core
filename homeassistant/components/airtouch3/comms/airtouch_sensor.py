"""Defines the Sensor class for representing a single sensor in an AirTouch system."""


class Sensor:
    """Represents an AirTouch sensor with temperature and availability state."""

    def __init__(self) -> None:
        """Initialize a new Sensor with default values for temperature and availability."""
        self._current_temperature = 0
        self._is_available = False

    @property
    def current_temperature(self) -> int:
        """Return the current measured temperature."""
        return self._current_temperature

    @current_temperature.setter
    def current_temperature(self, value: int) -> None:
        """Set the current measured temperature."""
        self._current_temperature = value

    @property
    def is_available(self) -> bool:
        """Return True if the sensor is operational, otherwise False."""
        return self._is_available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        """Set whether the sensor is operational."""
        self._is_available = value
