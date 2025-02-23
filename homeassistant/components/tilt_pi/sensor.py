"""Support for Tilt Hydrometer sensors."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass


class TiltHydrometer(SensorEntity):
    """Representation of a Tilt Hydrometer sensor."""

    def __init__(self, mac_id: str, color: str, temperature: int, gravity: int) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = mac_id
        self._attr_name = f"Tilt {color}"
        self._attr_native_value = temperature
        self._attr_native_unit_of_measurement = "°F"
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._mac_id = mac_id
        self._color = color
        self._temperature = temperature
        self._gravity = gravity

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the entity state attributes."""
        return {
            "mac_id": self._mac_id,
            "color": self._color,
            "temperature": self._temperature,
            "gravity": self._gravity,
        }

    # These below might not be necessary
    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Tilt {self._color}"

    @property
    def mac_id(self) -> str:
        """Return the MAC ID of the sensor."""
        return self._mac_id

    @property
    def temperature(self) -> int:
        """Return the temperature of the sensor."""
        return self._temperature

    @property
    def gravity(self) -> int:
        """Return the gravity of the sensor."""
        return self._gravity
