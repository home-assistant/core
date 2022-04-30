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
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import UnitSystem

from . import BMWConnectedDriveBaseEntity
from .const import DOMAIN, UNIT_MAP
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _condition_based_services(
    vehicle_state: VehicleStatus, unit_system: UnitSystem
) -> dict[str, Any]:
    extra_attributes = {}
    for report in vehicle_state.condition_based_services:
        extra_attributes.update(_format_cbs_report(report, unit_system))
    return extra_attributes


def _check_control_messages(vehicle_state: VehicleStatus) -> dict[str, Any]:
    extra_attributes: dict[str, Any] = {}
    if vehicle_state.has_check_control_messages:
        cbs_list = [
            message.description_short
            for message in vehicle_state.check_control_messages
        ]
        extra_attributes["check_control_messages"] = cbs_list
    else:
        extra_attributes["check_control_messages"] = "OK"
    return extra_attributes


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

    value_fn: Callable[[VehicleStatus], bool]


@dataclass
class BMWBinarySensorEntityDescription(
    BinarySensorEntityDescription, BMWRequiredKeysMixin
):
    """Describes BMW binary_sensor entity."""

    attr_fn: Callable[[VehicleStatus, UnitSystem], dict[str, Any]] | None = None


SENSOR_TYPES: tuple[BMWBinarySensorEntityDescription, ...] = (
    BMWBinarySensorEntityDescription(
        key="lids",
        name="Doors",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-door-lock",
        # device class opening: On means open, Off means closed
        value_fn=lambda s: not s.all_lids_closed,
        attr_fn=lambda s, u: {lid.name: lid.state.value for lid in s.lids},
    ),
    BMWBinarySensorEntityDescription(
        key="windows",
        name="Windows",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-door",
        # device class opening: On means open, Off means closed
        value_fn=lambda s: not s.all_windows_closed,
        attr_fn=lambda s, u: {window.name: window.state.value for window in s.windows},
    ),
    BMWBinarySensorEntityDescription(
        key="door_lock_state",
        name="Door lock state",
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:car-key",
        # device class lock: On means unlocked, Off means locked
        # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
        value_fn=lambda s: s.door_lock_state
        not in {LockState.LOCKED, LockState.SECURED},
        attr_fn=lambda s, u: {
            "door_lock_state": s.door_lock_state.value,
            "last_update_reason": s.last_update_reason,
        },
    ),
    BMWBinarySensorEntityDescription(
        key="lights_parking",
        name="Parking lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        icon="mdi:car-parking-lights",
        # device class light: On means light detected, Off means no light
        value_fn=lambda s: cast(bool, s.are_parking_lights_on),
        attr_fn=lambda s, u: {"lights_parking": s.parking_lights.value},
    ),
    BMWBinarySensorEntityDescription(
        key="condition_based_services",
        name="Condition based services",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:wrench",
        # device class problem: On means problem detected, Off means no problem
        value_fn=lambda s: not s.are_all_cbs_ok,
        attr_fn=_condition_based_services,
    ),
    BMWBinarySensorEntityDescription(
        key="check_control_messages",
        name="Control messages",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:car-tire-alert",
        # device class problem: On means problem detected, Off means no problem
        value_fn=lambda s: cast(bool, s.has_check_control_messages),
        attr_fn=lambda s, u: _check_control_messages(s),
    ),
    # electric
    BMWBinarySensorEntityDescription(
        key="charging_status",
        name="Charging status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        icon="mdi:ev-station",
        # device class power: On means power detected, Off means no power
        value_fn=lambda s: cast(bool, s.charging_status == ChargingState.CHARGING),
        attr_fn=lambda s, u: {
            "charging_status": s.charging_status.value,
            "last_charging_end_result": s.last_charging_end_result,
        },
    ),
    BMWBinarySensorEntityDescription(
        key="connection_status",
        name="Connection status",
        device_class=BinarySensorDeviceClass.PLUG,
        icon="mdi:car-electric",
        value_fn=lambda s: cast(str, s.connection_status) == "CONNECTED",
        attr_fn=lambda s, u: {"connection_status": s.connection_status},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        BMWConnectedDriveSensor(coordinator, vehicle, description, hass.config.units)
        for vehicle in coordinator.account.vehicles
        for description in SENSOR_TYPES
        if description.key in vehicle.available_attributes
    ]
    async_add_entities(entities)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    entity_description: BMWBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: ConnectedDriveVehicle,
        description: BMWBinarySensorEntityDescription,
        unit_system: UnitSystem,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._unit_system = unit_system

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Updating binary sensor '%s' of %s",
            self.entity_description.key,
            self.vehicle.name,
        )
        vehicle_state = self.vehicle.status

        self._attr_is_on = self.entity_description.value_fn(vehicle_state)

        if self.entity_description.attr_fn:
            self._attr_extra_state_attributes = dict(
                self._attrs,
                **self.entity_description.attr_fn(vehicle_state, self._unit_system),
            )

        super()._handle_coordinator_update()
