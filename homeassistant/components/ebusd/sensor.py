"""Support for Ebusd sensors."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .const import DOMAIN

TIME_FRAME1_BEGIN = "time_frame1_begin"
TIME_FRAME1_END = "time_frame1_end"
TIME_FRAME2_BEGIN = "time_frame2_begin"
TIME_FRAME2_END = "time_frame2_end"
TIME_FRAME3_BEGIN = "time_frame3_begin"
TIME_FRAME3_END = "time_frame3_end"
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

#  SensorTypes from ebusdpy module :
#  0='decimal', 1='time-schedule', 2='switch', 3='string', 4='value;status'

SENSOR_TYPES = {
    "700": {
        "ActualFlowTemperatureDesired": [
            "Hc1ActualFlowTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "MaxFlowTemperatureDesired": [
            "Hc1MaxFlowTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "MinFlowTemperatureDesired": [
            "Hc1MinFlowTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "PumpStatus": ["Hc1PumpStatus", None, "mdi:toggle-switch", 2, None],
        "HCSummerTemperatureLimit": [
            "Hc1SummerTempLimit",
            TEMP_CELSIUS,
            "mdi:weather-sunny",
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "HolidayTemperature": [
            "HolidayTemp",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "HWTemperatureDesired": [
            "HwcTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "HWActualTemperature": [
            "HwcStorageTemp",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "HWTimerMonday": ["hwcTimer.Monday", None, "mdi:timer-outline", 1, None],
        "HWTimerTuesday": ["hwcTimer.Tuesday", None, "mdi:timer-outline", 1, None],
        "HWTimerWednesday": ["hwcTimer.Wednesday", None, "mdi:timer-outline", 1, None],
        "HWTimerThursday": ["hwcTimer.Thursday", None, "mdi:timer-outline", 1, None],
        "HWTimerFriday": ["hwcTimer.Friday", None, "mdi:timer-outline", 1, None],
        "HWTimerSaturday": ["hwcTimer.Saturday", None, "mdi:timer-outline", 1, None],
        "HWTimerSunday": ["hwcTimer.Sunday", None, "mdi:timer-outline", 1, None],
        "HWOperativeMode": ["HwcOpMode", None, "mdi:math-compass", 3, None],
        "WaterPressure": ["WaterPressure", PRESSURE_BAR, "mdi:water-pump", 0, None],
        "Zone1RoomZoneMapping": ["z1RoomZoneMapping", None, "mdi:label", 0, None],
        "Zone1NightTemperature": [
            "z1NightTemp",
            TEMP_CELSIUS,
            "mdi:weather-night",
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Zone1DayTemperature": [
            "z1DayTemp",
            TEMP_CELSIUS,
            "mdi:weather-sunny",
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Zone1HolidayTemperature": [
            "z1HolidayTemp",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Zone1RoomTemperature": [
            "z1RoomTemp",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Zone1ActualRoomTemperatureDesired": [
            "z1ActualRoomTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Zone1TimerMonday": ["z1Timer.Monday", None, "mdi:timer-outline", 1, None],
        "Zone1TimerTuesday": ["z1Timer.Tuesday", None, "mdi:timer-outline", 1, None],
        "Zone1TimerWednesday": [
            "z1Timer.Wednesday",
            None,
            "mdi:timer-outline",
            1,
            None,
        ],
        "Zone1TimerThursday": ["z1Timer.Thursday", None, "mdi:timer-outline", 1, None],
        "Zone1TimerFriday": ["z1Timer.Friday", None, "mdi:timer-outline", 1, None],
        "Zone1TimerSaturday": ["z1Timer.Saturday", None, "mdi:timer-outline", 1, None],
        "Zone1TimerSunday": ["z1Timer.Sunday", None, "mdi:timer-outline", 1, None],
        "Zone1OperativeMode": ["z1OpMode", None, "mdi:math-compass", 3, None],
        "ContinuosHeating": [
            "ContinuosHeating",
            TEMP_CELSIUS,
            "mdi:weather-snowy",
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "PowerEnergyConsumptionLastMonth": [
            "PrEnergySumHcLastMonth",
            ENERGY_KILO_WATT_HOUR,
            "mdi:flash",
            0,
            None,
        ],
        "PowerEnergyConsumptionThisMonth": [
            "PrEnergySumHcThisMonth",
            ENERGY_KILO_WATT_HOUR,
            "mdi:flash",
            0,
            None,
        ],
    },
    "ehp": {
        "HWTemperature": [
            "HwcTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "OutsideTemp": [
            "OutsideTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
    },
    "bai": {
        "HotWaterTemperature": [
            "HwcTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "StorageTemperature": [
            "StorageTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "DesiredStorageTemperature": [
            "StorageTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "OutdoorsTemperature": [
            "OutdoorstempSensor",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "WaterPressure": ["WaterPressure", PRESSURE_BAR, "mdi:pipe", 4, None],
        "AverageIgnitionTime": [
            "averageIgnitiontime",
            TIME_SECONDS,
            "mdi:av-timer",
            0,
            None,
        ],
        "MaximumIgnitionTime": [
            "maxIgnitiontime",
            TIME_SECONDS,
            "mdi:av-timer",
            0,
            None,
        ],
        "MinimumIgnitionTime": [
            "minIgnitiontime",
            TIME_SECONDS,
            "mdi:av-timer",
            0,
            None,
        ],
        "ReturnTemperature": [
            "ReturnTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "CentralHeatingPump": ["WP", None, "mdi:toggle-switch", 2, None],
        "HeatingSwitch": ["HeatingSwitch", None, "mdi:toggle-switch", 2, None],
        "DesiredFlowTemperature": [
            "FlowTempDesired",
            TEMP_CELSIUS,
            None,
            0,
            SensorDeviceClass.TEMPERATURE,
        ],
        "FlowTemperature": [
            "FlowTemp",
            TEMP_CELSIUS,
            None,
            4,
            SensorDeviceClass.TEMPERATURE,
        ],
        "Flame": ["Flame", None, "mdi:toggle-switch", 2, None],
        "PowerEnergyConsumptionHeatingCircuit": [
            "PrEnergySumHc1",
            ENERGY_KILO_WATT_HOUR,
            "mdi:flash",
            0,
            None,
        ],
        "PowerEnergyConsumptionHotWaterCircuit": [
            "PrEnergySumHwc1",
            ENERGY_KILO_WATT_HOUR,
            "mdi:flash",
            0,
            None,
        ],
        "RoomThermostat": ["DCRoomthermostat", None, "mdi:toggle-switch", 2, None],
        "HeatingPartLoad": [
            "PartloadHcKW",
            ENERGY_KILO_WATT_HOUR,
            "mdi:flash",
            0,
            None,
        ],
        "StateNumber": ["StateNumber", None, "mdi:fire", 3, None],
        "ModulationPercentage": [
            "ModulationTempDesired",
            PERCENTAGE,
            "mdi:percent",
            0,
            None,
        ],
    },
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ebus sensor."""
    if not discovery_info:
        return
    ebusd_api = hass.data[DOMAIN]
    monitored_conditions = discovery_info["monitored_conditions"]
    name = discovery_info["client_name"]

    dev = []
    for condition in monitored_conditions:
        dev.append(
            EbusdSensor(ebusd_api, discovery_info["sensor_types"][condition], name)
        )

    add_entities(dev, True)


class EbusdSensor(SensorEntity):
    """Ebusd component sensor methods definition."""

    def __init__(self, data, sensor, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        (
            self._name,
            self._unit_of_measurement,
            self._icon,
            self._type,
            self._device_class,
        ) = sensor
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client_name} {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self._type == 1 and self._state is not None:
            schedule = {
                TIME_FRAME1_BEGIN: None,
                TIME_FRAME1_END: None,
                TIME_FRAME2_BEGIN: None,
                TIME_FRAME2_END: None,
                TIME_FRAME3_BEGIN: None,
                TIME_FRAME3_END: None,
            }
            time_frame = self._state.split(";")
            for index, item in enumerate(sorted(schedule.items())):
                if index < len(time_frame):
                    parsed = datetime.datetime.strptime(time_frame[index], "%H:%M")
                    parsed = parsed.replace(
                        dt_util.now().year, dt_util.now().month, dt_util.now().day
                    )
                    schedule[item[0]] = parsed.isoformat()
            return schedule
        return None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name, self._type)
            if self._name not in self.data.value:
                return

            self._state = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
