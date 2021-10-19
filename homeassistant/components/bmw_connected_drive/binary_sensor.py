"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

import logging

from bimmer_connected.state import ChargingState, LockState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import LENGTH_KILOMETERS

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveBaseEntity
from .const import CONF_ACCOUNT, DATA_ENTRIES

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="lids",
        name="Doors",
        device_class=DEVICE_CLASS_OPENING,
        icon="mdi:car-door-lock",
    ),
    BinarySensorEntityDescription(
        key="windows",
        name="Windows",
        device_class=DEVICE_CLASS_OPENING,
        icon="mdi:car-door",
    ),
    BinarySensorEntityDescription(
        key="door_lock_state",
        name="Door lock state",
        device_class="lock",
        icon="mdi:car-key",
    ),
    BinarySensorEntityDescription(
        key="lights_parking",
        name="Parking lights",
        device_class="light",
        icon="mdi:car-parking-lights",
    ),
    BinarySensorEntityDescription(
        key="condition_based_services",
        name="Condition based services",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:wrench",
    ),
    BinarySensorEntityDescription(
        key="check_control_messages",
        name="Control messages",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:car-tire-alert",
    ),
    # electric
    BinarySensorEntityDescription(
        key="charging_status",
        name="Charging status",
        device_class="power",
        icon="mdi:ev-station",
    ),
    BinarySensorEntityDescription(
        key="connection_status",
        name="Connection status",
        device_class=DEVICE_CLASS_PLUG,
        icon="mdi:car-electric",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    account = hass.data[BMW_DOMAIN][DATA_ENTRIES][config_entry.entry_id][CONF_ACCOUNT]

    entities = [
        BMWConnectedDriveSensor(account, vehicle, description)
        for vehicle in account.account.vehicles
        for description in SENSOR_TYPES
        if description.key in vehicle.available_attributes
    ]
    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    def __init__(self, account, vehicle, description: BinarySensorEntityDescription):
        """Initialize sensor."""
        super().__init__(account, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    def update(self):
        """Read new state data from the library."""
        sensor_type = self.entity_description.key
        vehicle_state = self._vehicle.state
        result = self._attrs.copy()

        # device class opening: On means open, Off means closed
        if sensor_type == "lids":
            _LOGGER.debug("Status of lid: %s", vehicle_state.all_lids_closed)
            self._attr_is_on = not vehicle_state.all_lids_closed
            for lid in vehicle_state.lids:
                result[lid.name] = lid.state.value
        elif sensor_type == "windows":
            self._attr_is_on = not vehicle_state.all_windows_closed
            for window in vehicle_state.windows:
                result[window.name] = window.state.value
        # device class lock: On means unlocked, Off means locked
        elif sensor_type == "door_lock_state":
            # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
            self._attr_is_on = vehicle_state.door_lock_state not in [
                LockState.LOCKED,
                LockState.SECURED,
            ]
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        # device class light: On means light detected, Off means no light
        elif sensor_type == "lights_parking":
            self._attr_is_on = vehicle_state.are_parking_lights_on
            result["lights_parking"] = vehicle_state.parking_lights.value
        # device class problem: On means problem detected, Off means no problem
        elif sensor_type == "condition_based_services":
            self._attr_is_on = not vehicle_state.are_all_cbs_ok
            for report in vehicle_state.condition_based_services:
                result.update(self._format_cbs_report(report))
        elif sensor_type == "check_control_messages":
            self._attr_is_on = vehicle_state.has_check_control_messages
            check_control_messages = vehicle_state.check_control_messages
            has_check_control_messages = vehicle_state.has_check_control_messages
            if has_check_control_messages:
                cbs_list = []
                for message in check_control_messages:
                    cbs_list.append(message.description_short)
                result["check_control_messages"] = cbs_list
            else:
                result["check_control_messages"] = "OK"
        # device class power: On means power detected, Off means no power
        elif sensor_type == "charging_status":
            self._attr_is_on = vehicle_state.charging_status in [ChargingState.CHARGING]
            result["charging_status"] = vehicle_state.charging_status.value
            result["last_charging_end_result"] = vehicle_state.last_charging_end_result
        # device class plug: On means device is plugged in,
        #                    Off means device is unplugged
        elif sensor_type == "connection_status":
            self._attr_is_on = vehicle_state.connection_status == "CONNECTED"
            result["connection_status"] = vehicle_state.connection_status

        self._attr_extra_state_attributes = result

    def _format_cbs_report(self, report):
        result = {}
        service_type = report.service_type.lower().replace("_", " ")
        result[f"{service_type} status"] = report.state.value
        if report.due_date is not None:
            result[f"{service_type} date"] = report.due_date.strftime("%Y-%m-%d")
        if report.due_distance is not None:
            distance = round(
                self.hass.config.units.length(report.due_distance, LENGTH_KILOMETERS)
            )
            result[
                f"{service_type} distance"
            ] = f"{distance} {self.hass.config.units.length_unit}"
        return result
