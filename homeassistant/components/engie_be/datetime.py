"""Datetime platform for the ENGIE Belgium integration."""

from dataclasses import replace
from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, override

from aioengiebelgium import (
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    EngieBeError,
)

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, MAX_DEPARTURE_AHEAD
from .coordinator import EngieBeVehicleData, EngieBeVehiclesCoordinator

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a departure time entity for each Smart Charge vehicle."""
    coordinator = entry.runtime_data.vehicles
    known_vehicles: set[int] = set()

    @callback
    def _async_add_vehicles() -> None:
        """Add the entities of the vehicles that are not known yet."""
        vehicles: dict[int, EngieBeVehicleData] | None = coordinator.data
        if vehicles is None:
            return
        new_vehicles = set(vehicles) - known_vehicles
        if not new_vehicles:
            return
        known_vehicles.update(new_vehicles)
        async_add_entities(
            EngieBeDepartureTime(coordinator, vehicle_id) for vehicle_id in new_vehicles
        )

    entry.async_on_unload(coordinator.async_add_listener(_async_add_vehicles))
    _async_add_vehicles()


class EngieBeDepartureTime(
    CoordinatorEntity[EngieBeVehiclesCoordinator], DateTimeEntity
):
    """Departure time of the latest Smart Charge session of a vehicle."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "departure_time"

    def __init__(
        self, coordinator: EngieBeVehiclesCoordinator, vehicle_id: int
    ) -> None:
        """Initialize the departure time entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        vehicle = coordinator.data[vehicle_id].vehicle
        self._attr_unique_id = f"{vehicle_id}_departure_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"vehicle_{vehicle_id}")},
            manufacturer=vehicle.brand_name,
            model=vehicle.model_name,
            name=vehicle.display_name or vehicle.model_name,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True while the vehicle has a Smart Charge session."""
        return super().available and self._vehicle_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the departure time of the latest session."""
        return self.coordinator.data[self._vehicle_id].departure

    @override
    async def async_set_value(self, value: datetime) -> None:
        """Set the departure time of the latest session."""
        if value > dt_util.utcnow() + MAX_DEPARTURE_AHEAD:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="departure_too_far",
                translation_placeholders={"days": str(MAX_DEPARTURE_AHEAD.days)},
            )
        client = self.coordinator.client
        try:
            latest = await client.async_get_latest_charging_session_charge_settings(
                self._vehicle_id
            )
            target_battery_level = latest.target_battery_level
            if target_battery_level is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_active_session"
                )
            updated = await client.async_update_latest_charging_session_charge_settings(
                self._vehicle_id,
                departure_time_override=value,
                target_battery_level=target_battery_level,
                direct=bool(latest.direct),
            )
        except EngieBeAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except EngieBeCommunicationError as err:
            if err.status == HTTPStatus.NOT_FOUND:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_active_session"
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except EngieBeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        self.coordinator.async_set_updated_data(
            {
                **self.coordinator.data,
                self._vehicle_id: replace(
                    self.coordinator.data[self._vehicle_id],
                    departure=updated.departure_time_override,
                    target_battery_level=target_battery_level,
                    direct=bool(latest.direct),
                ),
            }
        )
