"""Tests for the Sensibo integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pysensibo.model import MotionSensor, SensiboData, SensiboDevice

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {CONF_API_KEY: "1234567890"}


async def init_integration(
    hass: HomeAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
    version: int = 2,
    unique_id: str = "username",
) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    if not config:
        config = ENTRY_CONFIG

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=config,
        entry_id=entry_id,
        unique_id=unique_id,
        version=version,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


DATA_FROM_API = SensiboData(
    raw={
        "status": "success",
        "result": [
            {
                "id": "ABC999111",
                "qrId": "AAAAAAAAAA",
                "room": {"uid": "99TT99TT", "name": "Hallway", "icon": "Lounge"},
                "acState": {
                    "timestamp": {
                        "time": "2022-04-30T19:58:15.544787Z",
                        "secondsAgo": 0,
                    },
                    "on": False,
                    "mode": "fan",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "location": {
                    "id": "ZZZZZZZZZZZZ",
                    "name": "Home",
                    "latLon": [58.9806976, 20.5864297],
                    "address": ["Sealand 99", "Some county"],
                    "country": "United Country",
                    "createTime": {
                        "time": "2020-03-21T15:44:15Z",
                        "secondsAgo": 66543240,
                    },
                    "updateTime": None,
                    "features": [],
                    "geofenceTriggerRadius": 200,
                    "subscription": None,
                    "technician": None,
                    "shareAnalytics": False,
                    "occupancy": "n/a",
                },
                "accessPoint": {"ssid": "SENSIBO-I-99999", "password": None},
                "macAddress": "00:02:00:B6:00:00",
                "autoOffMinutes": None,
                "autoOffEnabled": False,
                "antiMoldTimer": None,
                "antiMoldConfig": None,
            }
        ],
    },
    parsed={
        "ABC999111": SensiboDevice(
            id="ABC999111",
            mac="00:02:00:B6:00:00",
            name="Hallway",
            ac_states={
                "timestamp": {"time": "2022-04-30T19:58:15.544787Z", "secondsAgo": 0},
                "on": False,
                "mode": "heat",
                "fanLevel": "high",
                "swing": "stopped",
                "horizontalSwing": "stopped",
                "light": "on",
            },
            temp=22.4,
            humidity=38,
            target_temp=25,
            hvac_mode="heat",
            device_on=True,
            fan_mode="high",
            swing_mode="stopped",
            horizontal_swing_mode="stopped",
            light_mode="on",
            available=True,
            hvac_modes=["cool", "heat", "dry", "auto", "fan", "off"],
            fan_modes=["quiet", "low", "medium"],
            swing_modes=[
                "stopped",
                "fixedTop",
                "fixedMiddleTop",
            ],
            horizontal_swing_modes=[
                "stopped",
                "fixedLeft",
                "fixedCenterLeft",
            ],
            light_modes=["on", "off"],
            temp_unit="C",
            temp_list=[18, 19, 20],
            temp_step=1,
            active_features=[
                "timestamp",
                "on",
                "mode",
                "fanLevel",
                "swing",
                "targetTemperature",
                "horizontalSwing",
                "light",
            ],
            full_features={
                "targetTemperature",
                "fanLevel",
                "swing",
                "horizontalSwing",
                "light",
            },
            state="heat",
            fw_ver="SKY30046",
            fw_ver_available="SKY30046",
            fw_type="esp8266ex",
            model="skyv2",
            calibration_temp=0.1,
            calibration_hum=0.1,
            full_capabilities={
                "modes": {
                    "cool": {
                        "temperatures": {
                            "F": {
                                "isNative": False,
                                "values": [
                                    64,
                                    66,
                                    68,
                                ],
                            },
                            "C": {
                                "isNative": True,
                                "values": [
                                    18,
                                    19,
                                    20,
                                ],
                            },
                        },
                        "fanLevels": [
                            "quiet",
                            "low",
                            "medium",
                        ],
                        "swing": [
                            "stopped",
                            "fixedTop",
                            "fixedMiddleTop",
                        ],
                        "horizontalSwing": [
                            "stopped",
                            "fixedLeft",
                            "fixedCenterLeft",
                        ],
                        "light": ["on", "off"],
                    },
                    "heat": {
                        "temperatures": {
                            "F": {
                                "isNative": False,
                                "values": [
                                    63,
                                    64,
                                    66,
                                ],
                            },
                            "C": {
                                "isNative": True,
                                "values": [
                                    17,
                                    18,
                                    19,
                                ],
                            },
                        },
                        "fanLevels": ["quiet", "low", "medium"],
                        "swing": [
                            "stopped",
                            "fixedTop",
                            "fixedMiddleTop",
                        ],
                        "horizontalSwing": [
                            "stopped",
                            "fixedLeft",
                            "fixedCenterLeft",
                        ],
                        "light": ["on", "off"],
                    },
                    "dry": {
                        "temperatures": {
                            "F": {
                                "isNative": False,
                                "values": [
                                    64,
                                    66,
                                    68,
                                ],
                            },
                            "C": {
                                "isNative": True,
                                "values": [
                                    18,
                                    19,
                                    20,
                                ],
                            },
                        },
                        "swing": [
                            "stopped",
                            "fixedTop",
                            "fixedMiddleTop",
                        ],
                        "horizontalSwing": [
                            "stopped",
                            "fixedLeft",
                            "fixedCenterLeft",
                        ],
                        "light": ["on", "off"],
                    },
                    "auto": {
                        "temperatures": {
                            "F": {
                                "isNative": False,
                                "values": [
                                    64,
                                    66,
                                    68,
                                ],
                            },
                            "C": {
                                "isNative": True,
                                "values": [
                                    18,
                                    19,
                                    20,
                                ],
                            },
                        },
                        "fanLevels": [
                            "quiet",
                            "low",
                            "medium",
                        ],
                        "swing": [
                            "stopped",
                            "fixedTop",
                            "fixedMiddleTop",
                        ],
                        "horizontalSwing": [
                            "stopped",
                            "fixedLeft",
                            "fixedCenterLeft",
                        ],
                        "light": ["on", "off"],
                    },
                    "fan": {
                        "temperatures": {},
                        "fanLevels": [
                            "quiet",
                            "low",
                        ],
                        "swing": [
                            "stopped",
                            "fixedTop",
                            "fixedMiddleTop",
                        ],
                        "horizontalSwing": [
                            "stopped",
                            "fixedLeft",
                            "fixedCenterLeft",
                        ],
                        "light": ["on", "off"],
                    },
                }
            },
            motion_sensors={
                "AABBCC": MotionSensor(
                    id="AABBCC",
                    alive=True,
                    motion=True,
                    fw_ver="V17",
                    fw_type="nrf52",
                    is_main_sensor=True,
                    battery_voltage=3000,
                    humidity=57,
                    temperature=23.9,
                    model="motion_sensor",
                    rssi=-72,
                )
            },
            pm25=None,
            room_occupied=True,
            update_available=False,
            schedules={},
            pure_boost_enabled=None,
            pure_sensitivity=None,
            pure_ac_integration=None,
            pure_geo_integration=None,
            pure_measure_integration=None,
            timer_on=False,
            timer_id=None,
            timer_state_on=None,
            timer_time=None,
            smart_on=False,
            smart_type="temperature",
            smart_low_temp_threshold=0.0,
            smart_high_temp_threshold=27.5,
            smart_low_state={
                "on": True,
                "targetTemperature": 21,
                "temperatureUnit": "C",
                "mode": "heat",
                "fanLevel": "low",
                "swing": "stopped",
                "horizontalSwing": "stopped",
                "light": "on",
            },
            smart_high_state={
                "on": True,
                "targetTemperature": 21,
                "temperatureUnit": "C",
                "mode": "cool",
                "fanLevel": "high",
                "swing": "stopped",
                "horizontalSwing": "stopped",
                "light": "on",
            },
            filter_clean=False,
            filter_last_reset="2022-03-12T15:24:26Z",
        ),
        "AAZZAAZZ": SensiboDevice(
            id="AAZZAAZZ",
            mac="00:01:00:01:00:01",
            name="Kitchen",
            ac_states={
                "timestamp": {"time": "2022-04-30T19:58:15.568753Z", "secondsAgo": 0},
                "on": False,
                "mode": "fan",
                "fanLevel": "low",
                "light": "on",
            },
            temp=None,
            humidity=None,
            target_temp=None,
            hvac_mode="off",
            device_on=False,
            fan_mode="low",
            swing_mode=None,
            horizontal_swing_mode=None,
            light_mode="on",
            available=True,
            hvac_modes=["fan", "off"],
            fan_modes=["low", "high"],
            swing_modes=None,
            horizontal_swing_modes=None,
            light_modes=["on", "dim", "off"],
            temp_unit="C",
            temp_list=[0, 1],
            temp_step=1,
            active_features=["timestamp", "on", "mode", "fanLevel", "light"],
            full_features={"light", "targetTemperature", "fanLevel"},
            state="off",
            fw_ver="PUR00111",
            fw_ver_available="PUR00111",
            fw_type="pure-esp32",
            model="pure",
            calibration_temp=0.0,
            calibration_hum=0.0,
            full_capabilities={
                "modes": {
                    "fan": {
                        "temperatures": {},
                        "fanLevels": ["low", "high"],
                        "light": ["on", "dim", "off"],
                    }
                }
            },
            motion_sensors={},
            pm25=1,
            room_occupied=None,
            update_available=False,
            schedules={},
            pure_boost_enabled=False,
            pure_sensitivity="N",
            pure_ac_integration=False,
            pure_geo_integration=False,
            pure_measure_integration=True,
            timer_on=None,
            timer_id=None,
            timer_state_on=None,
            timer_time=None,
            smart_on=None,
            smart_type=None,
            smart_low_temp_threshold=None,
            smart_high_temp_threshold=None,
            smart_low_state=None,
            smart_high_state=None,
            filter_clean=False,
            filter_last_reset="2022-04-23T15:58:45Z",
        ),
    },
)
