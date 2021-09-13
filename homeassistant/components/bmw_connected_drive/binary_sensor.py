"""Reads vehicle status from BMW connected drive portal."""
import logging

from bimmer_connected.state import ChargingState, LockState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import LENGTH_KILOMETERS

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveBaseEntity
from .const import CONF_ACCOUNT, DATA_ENTRIES

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "lids": ["Doors", DEVICE_CLASS_OPENING, "mdi:car-door-lock"],
    "windows": ["Windows", DEVICE_CLASS_OPENING, "mdi:car-door"],
    "door_lock_state": ["Door lock state", "lock", "mdi:car-key"],
    "lights_parking": ["Parking lights", "light", "mdi:car-parking-lights"],
    "condition_based_services": [
        "Condition based services",
        DEVICE_CLASS_PROBLEM,
        "mdi:wrench",
    ],
    "check_control_messages": [
        "Control messages",
        DEVICE_CLASS_PROBLEM,
        "mdi:car-tire-alert",
    ],
}

SENSOR_TYPES_ELEC = {
    "charging_status": ["Charging status", "power", "mdi:ev-station"],
    "connection_status": ["Connection status", DEVICE_CLASS_PLUG, "mdi:car-electric"],
}

SENSOR_TYPES_ELEC.update(SENSOR_TYPES)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    account = hass.data[BMW_DOMAIN][DATA_ENTRIES][config_entry.entry_id][CONF_ACCOUNT]
    entities = []

    for vehicle in account.account.vehicles:
        if vehicle.has_hv_battery:
            _LOGGER.debug("BMW with a high voltage battery")
            for key, value in sorted(SENSOR_TYPES_ELEC.items()):
                if key in vehicle.available_attributes:
                    device = BMWConnectedDriveSensor(
                        account, vehicle, key, value[0], value[1], value[2]
                    )
                    entities.append(device)
        elif vehicle.has_internal_combustion_engine:
            _LOGGER.debug("BMW with an internal combustion engine")
            for key, value in sorted(SENSOR_TYPES.items()):
                if key in vehicle.available_attributes:
                    device = BMWConnectedDriveSensor(
                        account, vehicle, key, value[0], value[1], value[2]
                    )
                    entities.append(device)
    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    def __init__(
        self, account, vehicle, attribute: str, sensor_name, device_class, icon
    ):
        """Initialize sensor."""
        super().__init__(account, vehicle)

        self._attribute = attribute
        self._attr_name = f"{vehicle.name} {attribute}"
        self._attr_unique_id = f"{vehicle.vin}-{attribute}"
        self._sensor_name = sensor_name
        self._attr_device_class = device_class
        self._attr_icon = icon

    def update(self):
        """Read new state data from the library."""
        vehicle_state = self._vehicle.state
        result = self._attrs.copy()

        # device class opening: On means open, Off means closed
        if self._attribute == "lids":
            _LOGGER.debug("Status of lid: %s", vehicle_state.all_lids_closed)
            self._attr_is_on = not vehicle_state.all_lids_closed
            for lid in vehicle_state.lids:
                result[lid.name] = lid.state.value
        elif self._attribute == "windows":
            self._attr_is_on = not vehicle_state.all_windows_closed
            for window in vehicle_state.windows:
                result[window.name] = window.state.value
        # device class lock: On means unlocked, Off means locked
        elif self._attribute == "door_lock_state":
            # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
            self._attr_is_on = vehicle_state.door_lock_state not in [
                LockState.LOCKED,
                LockState.SECURED,
            ]
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        # device class light: On means light detected, Off means no light
        elif self._attribute == "lights_parking":
            self._attr_is_on = vehicle_state.are_parking_lights_on
            result["lights_parking"] = vehicle_state.parking_lights.value
        # device class problem: On means problem detected, Off means no problem
        elif self._attribute == "condition_based_services":
            self._attr_is_on = not vehicle_state.are_all_cbs_ok
            for report in vehicle_state.condition_based_services:
                result.update(self._format_cbs_report(report))
        elif self._attribute == "check_control_messages":
            self._attr_is_on = vehicle_state.has_check_control_messages
            check_control_messages = vehicle_state.check_control_messages
            has_check_control_messages = vehicle_state.has_check_control_messages
            if has_check_control_messages:
                cbs_list = []
                for message in check_control_messages:
                    cbs_list.append(message["ccmDescriptionShort"])
                result["check_control_messages"] = cbs_list
            else:
                result["check_control_messages"] = "OK"
        # device class power: On means power detected, Off means no power
        elif self._attribute == "charging_status":
            self._attr_is_on = vehicle_state.charging_status in [ChargingState.CHARGING]
            result["charging_status"] = vehicle_state.charging_status.value
            result["last_charging_end_result"] = vehicle_state.last_charging_end_result
        # device class plug: On means device is plugged in,
        #                    Off means device is unplugged
        elif self._attribute == "connection_status":
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
