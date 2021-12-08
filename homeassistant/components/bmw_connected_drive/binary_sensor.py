"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from bimmer_connected.vehicle import ConnectedDriveVehicle
from bimmer_connected.vehicle_status import (
    ChargingState,
    ConditionBasedServiceReport,
    LockState,
    VehicleStatus,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import UnitSystem

from . import (
    DOMAIN as BMW_DOMAIN,
    BMWConnectedDriveAccount,
    BMWConnectedDriveBaseEntity,
)
from .const import CONF_ACCOUNT, DATA_ENTRIES, UNIT_MAP

_LOGGER = logging.getLogger(__name__)


def _are_doors_closed(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class opening: On means open, Off means closed
    _LOGGER.debug("Status of lid: %s", vehicle_state.all_lids_closed)
    for lid in vehicle_state.lids:
        extra_attributes[lid.name] = lid.state.value
    return not vehicle_state.all_lids_closed


def _are_windows_closed(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class opening: On means open, Off means closed
    for window in vehicle_state.windows:
        extra_attributes[window.name] = window.state.value
    return not vehicle_state.all_windows_closed


def _are_doors_locked(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class lock: On means unlocked, Off means locked
    # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
    extra_attributes["door_lock_state"] = vehicle_state.door_lock_state.value
    extra_attributes["last_update_reason"] = vehicle_state.last_update_reason
    return vehicle_state.door_lock_state not in {LockState.LOCKED, LockState.SECURED}


def _are_parking_lights_on(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class light: On means light detected, Off means no light
    extra_attributes["lights_parking"] = vehicle_state.parking_lights.value
    return cast(bool, vehicle_state.are_parking_lights_on)


def _are_problems_detected(
    vehicle_state: VehicleStatus,
    extra_attributes: dict[str, Any],
    unit_system: UnitSystem,
) -> bool:
    # device class problem: On means problem detected, Off means no problem
    for report in vehicle_state.condition_based_services:
        extra_attributes.update(_format_cbs_report(report, unit_system))
    return not vehicle_state.are_all_cbs_ok


def _check_control_messages(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class problem: On means problem detected, Off means no problem
    check_control_messages = vehicle_state.check_control_messages
    has_check_control_messages = vehicle_state.has_check_control_messages
    if has_check_control_messages:
        cbs_list = [message.description_short for message in check_control_messages]
        extra_attributes["check_control_messages"] = cbs_list
    else:
        extra_attributes["check_control_messages"] = "OK"
    return cast(bool, vehicle_state.has_check_control_messages)


def _is_vehicle_charging(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class power: On means power detected, Off means no power
    extra_attributes["charging_status"] = vehicle_state.charging_status.value
    extra_attributes[
        "last_charging_end_result"
    ] = vehicle_state.last_charging_end_result
    return cast(bool, vehicle_state.charging_status == ChargingState.CHARGING)


def _is_vehicle_plugged_in(
    vehicle_state: VehicleStatus, extra_attributes: dict[str, Any], *args: Any
) -> bool:
    # device class plug: On means device is plugged in,
    #                    Off means device is unplugged
    extra_attributes["connection_status"] = vehicle_state.connection_status
    return cast(str, vehicle_state.connection_status) == "CONNECTED"


def _format_cbs_report(
    report: ConditionBasedServiceReport, unit_system: UnitSystem
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    service_type = report.service_type.lower().replace("_", " ")
    result[f"{service_type} status"] = report.state.value
    if report.due_date is not None:
        result[f"{service_type} date"] = report.due_date.strftime("%Y-%m-%d")
    if report.due_distance is not None:
        distance = round(
            unit_system.length(
                report.due_distance[0],
                UNIT_MAP.get(report.due_distance[1], report.due_distance[1]),
            )
        )
        result[f"{service_type} distance"] = f"{distance} {unit_system.length_unit}"
    return result


@dataclass
class BMWRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VehicleStatus, dict[str, Any], UnitSystem], bool]


@dataclass
class BMWBinarySensorEntityDescription(
    BinarySensorEntityDescription, BMWRequiredKeysMixin
):
    """Describes BMW binary_sensor entity."""


SENSOR_TYPES: tuple[BMWBinarySensorEntityDescription, ...] = (
    BMWBinarySensorEntityDescription(
        key="lids",
        name="Doors",
        device_class=DEVICE_CLASS_OPENING,
        icon="mdi:car-door-lock",
        value_fn=_are_doors_closed,
    ),
    BMWBinarySensorEntityDescription(
        key="windows",
        name="Windows",
        device_class=DEVICE_CLASS_OPENING,
        icon="mdi:car-door",
        value_fn=_are_windows_closed,
    ),
    BMWBinarySensorEntityDescription(
        key="door_lock_state",
        name="Door lock state",
        device_class=DEVICE_CLASS_LOCK,
        icon="mdi:car-key",
        value_fn=_are_doors_locked,
    ),
    BMWBinarySensorEntityDescription(
        key="lights_parking",
        name="Parking lights",
        device_class=DEVICE_CLASS_LIGHT,
        icon="mdi:car-parking-lights",
        value_fn=_are_parking_lights_on,
    ),
    BMWBinarySensorEntityDescription(
        key="condition_based_services",
        name="Condition based services",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:wrench",
        value_fn=_are_problems_detected,
    ),
    BMWBinarySensorEntityDescription(
        key="check_control_messages",
        name="Control messages",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:car-tire-alert",
        value_fn=_check_control_messages,
    ),
    # electric
    BMWBinarySensorEntityDescription(
        key="charging_status",
        name="Charging status",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
        icon="mdi:ev-station",
        value_fn=_is_vehicle_charging,
    ),
    BMWBinarySensorEntityDescription(
        key="connection_status",
        name="Connection status",
        device_class=DEVICE_CLASS_PLUG,
        icon="mdi:car-electric",
        value_fn=_is_vehicle_plugged_in,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    account: BMWConnectedDriveAccount = hass.data[BMW_DOMAIN][DATA_ENTRIES][
        config_entry.entry_id
    ][CONF_ACCOUNT]

    entities = [
        BMWConnectedDriveSensor(account, vehicle, description, hass.config.units)
        for vehicle in account.account.vehicles
        for description in SENSOR_TYPES
        if description.key in vehicle.available_attributes
    ]
    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    entity_description: BMWBinarySensorEntityDescription

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
        description: BMWBinarySensorEntityDescription,
        unit_system: UnitSystem,
    ) -> None:
        """Initialize sensor."""
        super().__init__(account, vehicle)
        self.entity_description = description
        self._unit_system = unit_system

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug("Updating binary sensors of %s", self._vehicle.name)
        vehicle_state = self._vehicle.status
        result = self._attrs.copy()

        self._attr_is_on = self.entity_description.value_fn(
            vehicle_state, result, self._unit_system
        )
        self._attr_extra_state_attributes = result
