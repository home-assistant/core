"""Setup car sensors."""

from datetime import datetime

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DVSPortalConfigEntry
from .coordinator import DVSPortalCoordinator


class DVSCarSensor(CoordinatorEntity[DVSPortalCoordinator], Entity):
    """A car entity is a previously or future reserved car (identified by license plate).

    Its state indicates if the car is not present, reserved, or present.
    """

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry: DVSPortalConfigEntry, license_plate: str) -> None:
        """Register a new Car as entity."""
        super().__init__(config_entry.runtime_data.coordinator)

        self._license_plate = license_plate
        self._attr_unique_id = (
            f"dvsportal_{config_entry.entry_id}_carsensor_{license_plate.lower()}"
        )
        self._attr_extra_state_attributes = {}

        self._reset_attributes()
        self._set_state()

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
            f"{self._attr_extra_state_attributes.get('name')} ({self._license_plate})"
            if self._attr_extra_state_attributes.get("name")
            else f"Car {self._license_plate}"
        )

    def _reset_attributes(self):
        self._attr_extra_state_attributes = {
            "license_plate": self._license_plate,
            "name": self.coordinator.data.known_license_plates.get(self._license_plate),
        }
        history = self.coordinator.data.historic_reservations.get(
            self._license_plate, {}
        )
        self._attr_extra_state_attributes.update(
            {f"previous_{k}": v for k, v in history.items()}
        )

    def _set_state(self):
        """Set the current state of this car (license plate).

        The state can be present, reserved or not present.
        """
        reservation = self.coordinator.data.active_reservations.get(self._license_plate)
        if reservation is None:
            self._reset_attributes()
            self._attr_state = "not present"
        else:
            self._attr_extra_state_attributes.update(reservation)

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
                self._attr_state = "present"
            else:
                self._attr_state = "reserved"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._reset_attributes()
        self._set_state()

        self.async_write_ha_state()
