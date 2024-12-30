"""Setup balance and reservation sensors."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .entity import DVSCarSensor

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dvsportal"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dvsportal sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    async def async_add_car(new_license_plate: str):
        """Add new DVSCarSensor."""
        async_add_entities([DVSCarSensor(coordinator, new_license_plate)])

    def update_sensors_callback():
        # license plates
        ha_registered_license_plates: set[str] = set(
            hass.data[DOMAIN][config_entry.entry_id]["ha_registered_license_plates"]
        )
        known_license_plates: set[str] = set()
        if coordinator.data is not None:
            # sometimes coordinator.data is still None, if upstream api is slow..
            known_license_plates: set[str] = set(
                coordinator.data.get("known_license_plates", {}).keys()
            )

        new_license_plates = known_license_plates - ha_registered_license_plates

        for new_license_plate in new_license_plates:
            hass.async_create_task(async_add_car(new_license_plate))

        hass.data[DOMAIN][config_entry.entry_id]["ha_registered_license_plates"] = (
            known_license_plates
        )

    coordinator.async_add_listener(
        update_sensors_callback
    )  # make sure new kentekens are registered

    async_add_entities(
        [BalanceSensor(coordinator), ActiveReservationsSensor(coordinator)]
    )
    update_sensors_callback()  # add the kentekens at the start


class BalanceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Balance Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attributes: dict[str, Any] = {}

    @property
    def unique_id(self) -> str:
        """Only one balance sensor."""
        return "dvsportal_balance_unique_id"

    @property
    def icon(self) -> str:
        """An icon."""
        return "mdi:clock"

    @property
    def name(self) -> str:
        """Balance remaining."""
        return "Guest Parking Balance"

    @property
    def native_value(self) -> int:
        """Balance remaining."""
        self._attributes = self.coordinator.data["balance"]
        return self.coordinator.data["balance"]["balance"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes."""
        return self._attributes

    @property
    def native_unit_of_measurement(self) -> str:
        """Balance remaining in minutes."""
        return UnitOfTime.MINUTES

    @property
    def state_class(self) -> str:
        """Balance remaining total."""
        return "total"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Duration."""
        return SensorDeviceClass.DURATION


class ActiveReservationsSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Active Reservations Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attributes: dict[str, Any] = {}

    @property
    def unique_id(self) -> str:
        """Active reservations unique id."""
        return "dvsportal_active_reservations_unique_id"

    @property
    def icon(self) -> str:
        """Multiple cars."""
        return "mdi:car-multiple"

    @property
    def name(self) -> str:
        """Amount of current active reservations."""
        return "Reservations"

    @property
    def native_value(self) -> int:
        """Count all current and future reservations."""
        active_reservations = [
            v for k, v in self.coordinator.data.get("active_reservations", {}).items()
        ]

        now = datetime.now()

        active_licenseplates = []
        future_licenseplates = []

        for reservation in active_reservations:
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
            license_plate = reservation.get("license_plate")

            if license_plate:
                if valid_from <= now < valid_until:
                    active_licenseplates.append(license_plate)
                else:
                    future_licenseplates.append(license_plate)

        self._attributes = {
            "current_reservations": active_licenseplates,
            "future_reservationsthe": future_licenseplates,
        }
        return len(active_licenseplates) + len(future_licenseplates)

    @property
    def native_unit_of_measurement(self) -> str:
        """Amount of reservations."""
        return "reservations"

    @property
    def state_class(self) -> str:
        """Total."""
        return "total"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose attributes."""
        return self._attributes
