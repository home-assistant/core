"""Setup car sensors."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dvsportal"


class DVSCarSensor(CoordinatorEntity, Entity):
    """A car entity is a previously or future reserved car (identified by license plate).

    Its state indicates if the car is not present, reserved, or present.
    """

    def __init__(self, coordinator, license_plate: str) -> None:
        """Register a new Car as entity."""
        super().__init__(coordinator)

        self._license_plate = license_plate
        self._reset_attributes()

    @property
    def unique_id(self) -> str:
        """Unique identifier for this car."""
        return f"dvsportal_carsensor_{self._license_plate}"

    @property
    def icon(self) -> str:
        """The icon. Also indicates state."""
        return "mdi:car" if self.state == "not present" else "mdi:car-clock"

    @property
    def device_class(self) -> str:
        """Deviceclass. Allows for filtering."""
        return "dvs_car_sensor"

    @property
    def name(self) -> str:
        """Return the human readable name."""
        return (
            f"Car {self._license_plate}"
            if self._attributes.get("name") is None
            else f"{self._attributes.get('name')} ({self._license_plate})"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose extra attributes."""
        return self._attributes

    def _reset_attributes(self):
        self._attributes = {
            "license_plate": self._license_plate,
            "name": self.coordinator.data.get("known_license_plates", {}).get(
                self._license_plate
            ),
        }
        history = self.coordinator.data.get("historic_reservations", {}).get(
            self._license_plate, {}
        )
        self._attributes.update({f"previous_{k}": v for k, v in history.items()})

    @property
    def state(self) -> str:
        """The current state of this car (license plate).

        The state can be present, reserved or not present.
        """
        reservation = self.coordinator.data.get("active_reservations", {}).get(
            self._license_plate
        )
        if reservation is None:
            self._reset_attributes()
            return "not present"

        self._attributes.update(reservation)

        now = datetime.now()
        valid_until = datetime.strptime(
            str(reservation.get("valid_until", "1900-01-01T00:00:00")).split(
                ".", maxsplit=1
            )[0],
            "%Y-%m-%dT%H:%M:%S",
        )
        valid_from = datetime.strptime(
            str(reservation.get("valid_from", "1900-01-01T00:00:00")).split(
                ".", maxsplit=1
            )[0],
            "%Y-%m-%dT%H:%M:%S",
        )

        if valid_from <= now < valid_until:
            return "present"
        return "reserved"
