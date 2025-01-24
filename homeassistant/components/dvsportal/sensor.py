"""Setup balance and reservation sensors."""

from datetime import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DVSPortalConfigEntry
from .coordinator import DVSPortalCoordinator
from .entity import DVSCarSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DVSPortalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dvsportal sensors."""

    runtime_data = config_entry.runtime_data
    coordinator = runtime_data.coordinator

    async def async_add_car(new_license_plate: str):
        """Add new DVSCarSensor."""
        async_add_entities([DVSCarSensor(config_entry, new_license_plate)])

    def update_sensors_callback():
        # license plates

        ha_registered_license_plates: set[str] = set(
            runtime_data.ha_registered_license_plates
        )
        known_license_plates: set[str] = set()
        if coordinator.data is not None:
            # sometimes coordinator.data is still None, if upstream api is slow..
            known_license_plates: set[str] = set(
                coordinator.data.known_license_plates.keys()
            )

        new_license_plates = known_license_plates - ha_registered_license_plates

        for new_license_plate in new_license_plates:
            hass.async_create_task(async_add_car(new_license_plate))

        runtime_data.ha_registered_license_plates = known_license_plates

    coordinator.async_add_listener(
        update_sensors_callback
    )  # make sure new kentekens are registered

    async_add_entities(
        [BalanceSensor(config_entry), ActiveReservationsSensor(config_entry)]
    )
    update_sensors_callback()  # add the kentekens at the start


class BalanceSensor(CoordinatorEntity[DVSPortalCoordinator], SensorEntity):
    """Representation of a Balance Sensor."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: DVSPortalConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry.runtime_data.coordinator)
        self._attr_unique_id = f"dvsportal_{config_entry.entry_id}_balance"

    @property
    def icon(self) -> str:
        """An icon."""
        return "mdi:clock"

    @property
    def name(self) -> str:
        """Balance remaining."""
        return "Guest Parking Balance"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_native_value = self.coordinator.data.balance
        self.async_write_ha_state()

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


class ActiveReservationsSensor(CoordinatorEntity[DVSPortalCoordinator], SensorEntity):
    """Representation of an Active Reservations Sensor."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: DVSPortalConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry.runtime_data.coordinator)
        self._attr_unique_id = f"dvsportal_{config_entry.entry_id}_active_reservations"

    @property
    def icon(self) -> str:
        """Multiple cars."""
        return "mdi:car-multiple"

    @property
    def name(self) -> str:
        """Amount of current active reservations."""
        return "Reservations"

    def _set_state(self) -> None:
        """Calculate count of current and future reservations."""
        active_reservations = list(self.coordinator.data.active_reservations.values())

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

        self._attr_extra_state_attributes = {
            "current_reservations": active_licenseplates,
            "future_reservationsthe": future_licenseplates,
        }
        self._attr_native_value = len(active_licenseplates) + len(future_licenseplates)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state()
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self) -> str:
        """Amount of reservations."""
        return "reservations"

    @property
    def state_class(self) -> str:
        """Total."""
        return "total"
