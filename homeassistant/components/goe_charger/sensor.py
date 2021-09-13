"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ELECTRIC_POTENTIAL_VOLT, ELECTRIC_CURRENT_AMPERE, POWER_WATT, POWER_KILO_WATT, FREQUENCY_HERTZ, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR, TEMP_CELSIUS,
    SIGNAL_STRENGTH_DECIBELS, DEVICE_CLASS_CURRENT, DEVICE_CLASS_ENERGY, DEVICE_CLASS_POWER_FACTOR, DEVICE_CLASS_POWER, DEVICE_CLASS_SIGNAL_STRENGTH, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_VOLTAGE)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, STATE_CLASS_TOTAL_INCREASING
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN

POWER_FACTOR: Final = "%"

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    serial = config_entry.data["serial"]

    def car_state_data(data):
        car_state_texts = {
            0:  "Unknown",
            1:  "Idle",
            2:  "Charging",
            3:  "WaitCar",
            4:  "Complete",
            5:  "Error"
        }

        if data["car"] in car_state_texts:
            return car_state_texts[data["car"]]

        return "Unknown (" + str(data["car"]) + ")"

    def error_data(data):
        error_texts = {
            0:  "None",
            1:  "FiAc",
            2:  "FiDc",
            3:  "Phase",
            4:  "Overvolt",
            5:  "Overamp",
            6:  "Diode",
            7:  "PpInvalid",
            8:  "GndInvalid",
            9:  "ContactorStuck",
            10: "ContactorMiss",
            11: "FiUnknown",
            12: "Unknown",
            13: "Overtemp",
            14: "NoComm",
            15: "StatusLockStuckOpen",
            16: "StatusLockStuckLocked",
            17: "Reserved20",
            18: "Reserved21",
            19: "Reserved22",
            20: "Reserved23",
            21: "Reserved24"
        }

        if data["err"] in error_texts:
            return error_texts[data["err"]]

        return "Unknown (" + str(data["err"]) + ")"

    def model_status_data(data):
        model_status_texts = {
            0:  "NotChargingBecauseNoChargeCtrlData",
            1:  "NotChargingBecauseOvertemperature",
            2:  "NotChargingBecauseAccessControlWait",
            3:  "ChargingBecauseForceStateOn",
            4:  "NotChargingBecauseForceStateOff",
            5:  "NotChargingBecauseScheduler",
            6:  "NotChargingBecauseEnergyLimit",
            7:  "ChargingBecauseAwattarPriceLow",
            8:  "ChargingBecauseAutomaticStopTestLadung",
            9:  "ChargingBecauseAutomaticStopNotEnoughTime",
            10: "ChargingBecauseAutomaticStop",
            11: "ChargingBecauseAutomaticStopNoClock",
            12: "ChargingBecausePvSurplus",
            13: "ChargingBecauseFallbackGoEDefault",
            14: "ChargingBecauseFallbackGoEScheduler",
            15: "ChargingBecauseFallbackDefault",
            16: "NotChargingBecauseFallbackGoEAwattar",
            17: "NotChargingBecauseFallbackAwattar",
            18: "NotChargingBecauseFallbackAutomaticStop",
            19: "ChargingBecauseCarCompatibilityKeepAlive",
            20: "ChargingBecauseChargePauseNotAllowed",
            22: "NotChargingBecauseSimulateUnplugging",
            23: "NotChargingBecausePhaseSwitch",
            24: "NotChargingBecauseMinPauseDuration"
        }

        if data["modelStatus"] in model_status_texts:
            return model_status_texts[data["modelStatus"]]

        return "Unknown (" + str(data["modelStatus"]) + ")"

    async_add_entities([
        GoeChargerSensor(coordinator, "Voltage L1",           serial, "voltage_l1",          ELECTRIC_POTENTIAL_VOLT,  DEVICE_CLASS_VOLTAGE,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][0] ),
        GoeChargerSensor(coordinator, "Voltage L2",           serial, "voltage_l2",          ELECTRIC_POTENTIAL_VOLT,  DEVICE_CLASS_VOLTAGE,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][1] ),
        GoeChargerSensor(coordinator, "Voltage L3",           serial, "voltage_l3",          ELECTRIC_POTENTIAL_VOLT,  DEVICE_CLASS_VOLTAGE,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][2] ),
        GoeChargerSensor(coordinator, "Voltage N",            serial, "voltage_n",           ELECTRIC_POTENTIAL_VOLT,  DEVICE_CLASS_VOLTAGE,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][3] ),
        GoeChargerSensor(coordinator, "Current L1",           serial, "current_l1",          ELECTRIC_CURRENT_AMPERE,  DEVICE_CLASS_CURRENT,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][4] ),
        GoeChargerSensor(coordinator, "Current L2",           serial, "current_l2",          ELECTRIC_CURRENT_AMPERE,  DEVICE_CLASS_CURRENT,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][5] ),
        GoeChargerSensor(coordinator, "Current L3",           serial, "current_l3",          ELECTRIC_CURRENT_AMPERE,  DEVICE_CLASS_CURRENT,         STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][6] ),
        GoeChargerSensorNative(coordinator, "Power L1",       serial, "power_l1",            POWER_KILO_WATT,          DEVICE_CLASS_POWER,           STATE_CLASS_MEASUREMENT,      "nrg", (lambda data: data["nrg"][7] / 1000) ,  POWER_KILO_WATT, lambda data: data["nrg"][7] ),
        GoeChargerSensorNative(coordinator, "Power L2",       serial, "power_l2",            POWER_KILO_WATT,          DEVICE_CLASS_POWER,           STATE_CLASS_MEASUREMENT,      "nrg", (lambda data: data["nrg"][8] / 1000) ,  POWER_KILO_WATT, lambda data: data["nrg"][8] ),
        GoeChargerSensorNative(coordinator, "Power L3",       serial, "power_l3",            POWER_KILO_WATT,          DEVICE_CLASS_POWER,           STATE_CLASS_MEASUREMENT,      "nrg", (lambda data: data["nrg"][9] / 1000) ,  POWER_KILO_WATT, lambda data: data["nrg"][9] ),
        GoeChargerSensorNative(coordinator, "Power N",        serial, "power_n",             POWER_KILO_WATT,          DEVICE_CLASS_POWER,           STATE_CLASS_MEASUREMENT,      "nrg", (lambda data: data["nrg"][10] / 1000) , POWER_KILO_WATT, lambda data: data["nrg"][10] ),
        GoeChargerSensorNative(coordinator, "Power Total",    serial, "power_total",         POWER_KILO_WATT,          DEVICE_CLASS_POWER,           STATE_CLASS_MEASUREMENT,      "nrg", (lambda data: data["nrg"][11] / 1000) , POWER_KILO_WATT, lambda data: data["nrg"][11] ),
        GoeChargerSensor(coordinator, "Powerfactor L1",       serial, "powerfactor_l1",      POWER_FACTOR,             DEVICE_CLASS_POWER_FACTOR,    STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][12] ),
        GoeChargerSensor(coordinator, "Powerfactor L2",       serial, "powerfactor_l2",      POWER_FACTOR,             DEVICE_CLASS_POWER_FACTOR,    STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][13] ),
        GoeChargerSensor(coordinator, "Powerfactor L3",       serial, "powerfactor_l3",      POWER_FACTOR,             DEVICE_CLASS_POWER_FACTOR,    STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][14] ),
        GoeChargerSensor(coordinator, "Powerfactor N",        serial, "powerfactor_n",       POWER_FACTOR,             DEVICE_CLASS_POWER_FACTOR,    STATE_CLASS_MEASUREMENT,      "nrg", lambda data: data["nrg"][15] ),
        GoeChargerSensor(coordinator, "Frequency",            serial, "frequency",           FREQUENCY_HERTZ,          None,                         STATE_CLASS_MEASUREMENT,      "fhz", lambda data: data["fhz"] ),
        GoeChargerSensorNative(coordinator, "Charged",        serial, "charged",             ENERGY_KILO_WATT_HOUR,    DEVICE_CLASS_ENERGY,          STATE_CLASS_TOTAL_INCREASING, "wh", (lambda data: data["wh"] / 1000) ,      POWER_KILO_WATT, lambda data: data["wh"] ),
        GoeChargerSensorNative(coordinator, "Charged total",  serial, "charged_total",       ENERGY_KILO_WATT_HOUR,    DEVICE_CLASS_ENERGY,          STATE_CLASS_TOTAL_INCREASING, "eto", (lambda data: data["eto"] / 1000) ,     POWER_KILO_WATT, lambda data: data["eto"] ),
        GoeChargerSensor(coordinator, "Temperature 1",        serial, "temperature_1",       TEMP_CELSIUS,             DEVICE_CLASS_TEMPERATURE,     STATE_CLASS_MEASUREMENT,      "tma", lambda data: data["tma"][0] ),
        GoeChargerSensor(coordinator, "Temperature 2",        serial, "temperature_2",       TEMP_CELSIUS,             DEVICE_CLASS_TEMPERATURE,     STATE_CLASS_MEASUREMENT,      "tma", lambda data: data["tma"][1] ),
        GoeChargerSensor(coordinator, "WiFi RSSI",            serial, "wifi_rssi",           SIGNAL_STRENGTH_DECIBELS, DEVICE_CLASS_SIGNAL_STRENGTH, STATE_CLASS_MEASUREMENT,      "rssi", lambda data: data["rssi"] ),
        GoeChargerSensor(coordinator, "Cable current limit",  serial, "cable_current_limit", ELECTRIC_CURRENT_AMPERE,  DEVICE_CLASS_CURRENT,         None,                         "cbl", lambda data: data["cbl"]),
        GoeChargerSensor(coordinator, "Allowed current",      serial, "allowed_current",     ELECTRIC_CURRENT_AMPERE,  DEVICE_CLASS_CURRENT,         None,                         "acu", lambda data: "" if data["acu"] is None else data["acu"] ),
        GoeChargerSensor(coordinator, "Car state",            serial, "car_state",           None,                     None,                         None,                         "car", car_state_data ),
        GoeChargerSensor(coordinator, "Error",                serial, "error",               None,                     None,                         None,                         "err", error_data ),
        GoeChargerSensor(coordinator, "Model status",         serial, "model_status",        None,                     None,                         None,                         "modelStatus", model_status_data ),
    ])

class GoeChargerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, name: str, serial: str, unique_id: str, unit_of_measurement: str | None, device_class: str | None, state_class: str | None, key: str, state_cb):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._name = name
        self._serial = serial
        self._unique_id = unique_id
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class
        self._state_class = state_class
        self._key = key
        self._state_cb = state_cb

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return "goe_charger_" + self._serial + "_" + self._unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None and self._key in self.coordinator.data

    @property
    def state(self):
        """Return the state of the sensor."""
        return None if not self.available else self._state_cb(self.coordinator.data)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self):
        """Return the state class."""
        return self._state_class

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Get attributes about the device."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            #"name": self._device.label,
            #"model": self._device.device_type_name,
            #"manufacturer": "Unavailable",
        }

class GoeChargerSensorNative(GoeChargerSensor):
    """Representation of a Sensor with separated native unit/value."""

    def __init__(self, coordinator: DataUpdateCoordinator, name: str, serial: str, unique_id: str, unit_of_measurement: str | None, device_class: str | None, state_class: str | None, key: str, state_cb, native_unit_of_measurement: str | None, native_state_cb):
        """Pass coordinator to GoeChargerSensor."""
        super().__init__(coordinator, name, serial, unique_id, unit_of_measurement, device_class, state_class, key, state_cb)
        self._native_unit_of_measurement = native_unit_of_measurement
        self._native_state_cb = native_state_cb

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        return None if not self.available else self._native_state_cb(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        return self._native_unit_of_measurement
