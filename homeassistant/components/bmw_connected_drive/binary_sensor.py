"""Reads vehicle status from BMW MyBMW portal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.doors_windows import LockState
from bimmer_connected.vehicle.fuel_and_battery import ChargingState
from bimmer_connected.vehicle.reports import ConditionBasedService

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import UnitSystem

from . import BMWConfigEntry
from .const import UNIT_MAP
from .coordinator import BMWDataUpdateCoordinator
from .entity import BMWBaseEntity

_LOGGER = logging.getLogger(__name__)


ALLOWED_CONDITION_BASED_SERVICE_KEYS = {
    "BRAKE_FLUID",
    "BRAKE_PADS_FRONT",
    "BRAKE_PADS_REAR",
    "EMISSION_CHECK",
    "ENGINE_OIL",
    "OIL",
    "TIRE_WEAR_FRONT",
    "TIRE_WEAR_REAR",
    "VEHICLE_CHECK",
    "VEHICLE_TUV",
}
LOGGED_CONDITION_BASED_SERVICE_WARNINGS: set[str] = set()

ALLOWED_CHECK_CONTROL_MESSAGE_KEYS = {
    "ENGINE_OIL",
    "TIRE_PRESSURE",
    "WASHING_FLUID",
}
LOGGED_CHECK_CONTROL_MESSAGE_WARNINGS: set[str] = set()


def _condition_based_services(
    vehicle: MyBMWVehicle, unit_system: UnitSystem
) -> dict[str, Any]:
    extra_attributes = {}
    for report in vehicle.condition_based_services.messages:
        if (
            report.service_type not in ALLOWED_CONDITION_BASED_SERVICE_KEYS
            and report.service_type not in LOGGED_CONDITION_BASED_SERVICE_WARNINGS
        ):
            _LOGGER.warning(
                "'%s' not an allowed condition based service (%s)",
                report.service_type,
                report,
            )
            LOGGED_CONDITION_BASED_SERVICE_WARNINGS.add(report.service_type)
            continue

        extra_attributes.update(_format_cbs_report(report, unit_system))
    return extra_attributes


def _check_control_messages(vehicle: MyBMWVehicle) -> dict[str, Any]:
    extra_attributes: dict[str, Any] = {}
    for message in vehicle.check_control_messages.messages:
        if (
            message.description_short not in ALLOWED_CHECK_CONTROL_MESSAGE_KEYS
            and message.description_short not in LOGGED_CHECK_CONTROL_MESSAGE_WARNINGS
        ):
            _LOGGER.warning(
                "'%s' not an allowed check control message (%s)",
                message.description_short,
                message,
            )
            LOGGED_CHECK_CONTROL_MESSAGE_WARNINGS.add(message.description_short)
            continue

        extra_attributes[message.description_short.lower()] = message.state.value
    return extra_attributes


def _format_cbs_report(
    report: ConditionBasedService, unit_system: UnitSystem
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    service_type = report.service_type.lower()
    result[service_type] = report.state.value
    if report.due_date is not None:
        result[f"{service_type}_date"] = report.due_date.strftime("%Y-%m-%d")
    if report.due_distance.value and report.due_distance.unit:
        distance = round(
            unit_system.length(
                report.due_distance.value,
                UNIT_MAP.get(report.due_distance.unit, report.due_distance.unit),
            )
        )
        result[f"{service_type}_distance"] = f"{distance} {unit_system.length_unit}"
    return result


@dataclass(frozen=True, kw_only=True)
class BMWBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes BMW binary_sensor entity."""

    value_fn: Callable[[MyBMWVehicle], bool]
    attr_fn: Callable[[MyBMWVehicle, UnitSystem], dict[str, Any]] | None = None
    is_available: Callable[[MyBMWVehicle], bool] = lambda v: v.is_lsc_enabled


SENSOR_TYPES: tuple[BMWBinarySensorEntityDescription, ...] = (
    BMWBinarySensorEntityDescription(
        key="lids",
        translation_key="lids",
        device_class=BinarySensorDeviceClass.OPENING,
        # device class opening: On means open, Off means closed
        value_fn=lambda v: not v.doors_and_windows.all_lids_closed,
        attr_fn=lambda v, u: {
            lid.name: lid.state.value for lid in v.doors_and_windows.lids
        },
    ),
    BMWBinarySensorEntityDescription(
        key="windows",
        translation_key="windows",
        device_class=BinarySensorDeviceClass.OPENING,
        # device class opening: On means open, Off means closed
        value_fn=lambda v: not v.doors_and_windows.all_windows_closed,
        attr_fn=lambda v, u: {
            window.name: window.state.value for window in v.doors_and_windows.windows
        },
    ),
    BMWBinarySensorEntityDescription(
        key="door_lock_state",
        translation_key="door_lock_state",
        device_class=BinarySensorDeviceClass.LOCK,
        # device class lock: On means unlocked, Off means locked
        # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
        value_fn=lambda v: v.doors_and_windows.door_lock_state
        not in {LockState.LOCKED, LockState.SECURED},
        attr_fn=lambda v, u: {
            "door_lock_state": v.doors_and_windows.door_lock_state.value
        },
    ),
    BMWBinarySensorEntityDescription(
        key="condition_based_services",
        translation_key="condition_based_services",
        device_class=BinarySensorDeviceClass.PROBLEM,
        # device class problem: On means problem detected, Off means no problem
        value_fn=lambda v: v.condition_based_services.is_service_required,
        attr_fn=_condition_based_services,
    ),
    BMWBinarySensorEntityDescription(
        key="check_control_messages",
        translation_key="check_control_messages",
        device_class=BinarySensorDeviceClass.PROBLEM,
        # device class problem: On means problem detected, Off means no problem
        value_fn=lambda v: v.check_control_messages.has_check_control_messages,
        attr_fn=lambda v, u: _check_control_messages(v),
    ),
    # electric
    BMWBinarySensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        # device class power: On means power detected, Off means no power
        value_fn=lambda v: v.fuel_and_battery.charging_status == ChargingState.CHARGING,
        is_available=lambda v: v.has_electric_drivetrain,
    ),
    BMWBinarySensorEntityDescription(
        key="connection_status",
        translation_key="connection_status",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda v: v.fuel_and_battery.is_charger_connected,
        is_available=lambda v: v.has_electric_drivetrain,
    ),
    BMWBinarySensorEntityDescription(
        key="is_pre_entry_climatization_enabled",
        translation_key="is_pre_entry_climatization_enabled",
        value_fn=lambda v: v.charging_profile.is_pre_entry_climatization_enabled
        if v.charging_profile
        else False,
        is_available=lambda v: v.has_electric_drivetrain,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMWConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW binary sensors from config entry."""
    coordinator = config_entry.runtime_data.coordinator

    entities = [
        BMWBinarySensor(coordinator, vehicle, description, hass.config.units)
        for vehicle in coordinator.account.vehicles
        for description in SENSOR_TYPES
        if description.is_available(vehicle)
    ]
    async_add_entities(entities)


class BMWBinarySensor(BMWBaseEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    entity_description: BMWBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWBinarySensorEntityDescription,
        unit_system: UnitSystem,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._unit_system = unit_system
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Updating binary sensor '%s' of %s",
            self.entity_description.key,
            self.vehicle.name,
        )
        self._attr_is_on = self.entity_description.value_fn(self.vehicle)

        if self.entity_description.attr_fn:
            self._attr_extra_state_attributes = self.entity_description.attr_fn(
                self.vehicle, self._unit_system
            )

        super()._handle_coordinator_update()
