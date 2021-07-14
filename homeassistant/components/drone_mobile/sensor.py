from datetime import datetime, timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, dt

from . import DroneMobileEntity
from .const import CONF_UNIT, DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Entities from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []
    for key, value in SENSORS.items():
        async_add_entities([CarSensor(entry, key, config_entry.options)], True)
        
class CarSensor(DroneMobileEntity,Entity,):
    def __init__(self, coordinator, sensor, options):
        self._sensor = sensor
        self.options = options
        self._attr = {}
        self.coordinator = coordinator
        self._device_id = "dronemobile_" + sensor

    def get_value(self, ftype):
        if ftype == "state":
            if self._sensor == "odometer":
                if self.options[CONF_UNIT] == "imperial":
                    return self.coordinator.data["last_known_state"]["mileage"]
                else:
                    return round(
                        float(self.coordinator.data["last_known_state"]["mileage"]) * 1.60934
                    )
            elif self._sensor == "battery":
                return self.coordinator.data["last_known_state"]["controller"]["main_battery_voltage"]
            elif self._sensor == "temperature":
                if self.options[CONF_UNIT] == "imperial":
                    return round(
                        float((self.coordinator.data["last_known_state"]["controller"]["current_temperature"]) * (9/5)) + 32
                    )
                else:
                    return self.coordinator.data["last_known_state"]["controller"]["current_temperature"]
            elif self._sensor == "gps":
                if self.coordinator.data["last_known_state"]["gps_direction"] == None:
                    return "Unsupported"
                return self.coordinator.data["last_known_state"]["gps_direction"]
            elif self._sensor == "alarm":
                if self.coordinator.data["last_known_state"]["controller"]["armed"] == True:
                    return "Armed"
                return "Disarmed"
            elif self._sensor == "ignitionStatus":
                if self.coordinator.data["last_known_state"]["controller"]["ignition_on"] == True:
                    return "On"
                else:
                    # Vehicle may have been remote started or stopped outside of Home Assistant, so we reset this flag to match the current vehicle status.
                    if self.coordinator.data["remote_start_status"] == True:
                        self.coordinator.data["remote_start_status"] = False
                    return "Off"
            elif self._sensor == "engineStatus":
                if self.coordinator.data["last_known_state"]["controller"]["engine_on"] == True:
                    return "Running"
                else:
                    # Vehicle may have been remote started or stopped outside of Home Assistant, so we reset this flag to match the current vehicle status.
                    if self.coordinator.data["remote_start_status"] == True:
                        self.coordinator.data["remote_start_status"] = False
                    return "Off"
            elif self._sensor == "doorStatus":
                if self.coordinator.data["last_known_state"]["controller"]["door_open"] == True:
                    return "Open"
                return "Closed"
            elif self._sensor == "trunkStatus":
                if self.coordinator.data["last_known_state"]["controller"]["trunk_open"] == True:
                    return "Open"
                return "Closed"
            elif self._sensor == "hoodStatus":
                if self.coordinator.data["last_known_state"]["controller"]["hood_open"] == True:
                    return "Open"
                return "Closed"
            elif self._sensor == "lastRefresh":
                return dt.as_local(
                    datetime.strptime(
                        self.coordinator.data["last_known_state"]["timestamp"], "%Y-%m-%dT%H:%M:%S%z"
                    )
                )
        elif ftype == "measurement":
            if self._sensor == "odometer":
                if self.options[CONF_UNIT] == "imperial":
                    return "mi"
                else:
                    return "km"
            elif self._sensor == "battery":
                return "V"
            elif self._sensor == "temperature":
                if self.options[CONF_UNIT] == "imperial":
                    return "°F"
                else:
                    return "°C"
            elif self._sensor == "gps":
                return None
            elif self._sensor == "alarm":
                return None
            elif self._sensor == "ignitionStatus":
                return None
            elif self._sensor == "engineStatus":
                return None
            elif self._sensor == "doorStatus":
                return None
            elif self._sensor == "trunkStatus":
                return None
            elif self._sensor == "hoodStatus":
                return None
            elif self._sensor == "lastRefresh":
                return None
        elif ftype == "attribute":
            if self._sensor == "odometer":
                return self.coordinator.data.items()
            elif self._sensor == "battery":
                return {
                    "Battery Voltage": self.coordinator.data["last_known_state"]["controller"]["main_battery_voltage"]
                }
            elif self._sensor == "temperature":
                return self.coordinator.data.items()
            elif self._sensor == "gps":
                if self.coordinator.data["last_known_state"]["gps_direction"] == None:
                    return None
                return self.coordinator.data.items()
            elif self._sensor == "alarm":
                return self.coordinator.data.items()
            elif self._sensor == "ignitionStatus":
                return self.coordinator.data.items()
            elif self._sensor == "engineStatus":
                return self.coordinator.data.items()
            elif self._sensor == "doorStatus":
                return self.coordinator.data.items()
            elif self._sensor == "trunkStatus":
                return self.coordinator.data.items()
            elif self._sensor == "hoodStatus":
                return self.coordinator.data.items()
            elif self._sensor == "lastRefresh":
                return None
            else:
                return None

    @property
    def name(self):
        return self.coordinator.data["vehicle_name"] + "_" + self._sensor

    @property
    def state(self):
        return self.get_value("state")

    @property
    def device_id(self):
        return self.device_id

    @property
    def device_state_attributes(self):
        return self.get_value("attribute")

    @property
    def unit_of_measurement(self):
        return self.get_value("measurement")

    @property
    def icon(self):
        return SENSORS[self._sensor]["icon"]
