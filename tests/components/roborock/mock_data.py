"""Mock data for Roborock tests."""
from __future__ import annotations

from roborock.containers import (
    CleanRecord,
    CleanSummary,
    Consumable,
    DNDTimer,
    HomeData,
    Status,
    UserData,
)
from roborock.typing import RoborockDeviceProp

# All data is based on a U.S. customer with a Roborock S7 MaxV Ultra
USER_EMAIL = "user@domain.com"

BASE_URL = "https://usiot.roborock.com"

USER_DATA = UserData.from_dict(
    {
        "tuyaname": "abc123",
        "tuyapwd": "abc123",
        "uid": 123456,
        "tokentype": "",
        "token": "abc123",
        "rruid": "abc123",
        "region": "us",
        "countrycode": "1",
        "country": "US",
        "nickname": "user_nickname",
        "rriot": {
            "u": "abc123",
            "s": "abc123",
            "h": "abc123",
            "k": "abc123",
            "r": {
                "r": "US",
                "a": "https://api-us.roborock.com",
                "m": "ssl://mqtt-us-2.roborock.com:8883",
                "l": "https://wood-us.roborock.com",
            },
        },
        "tuyaDeviceState": 2,
        "avatarurl": "https://files.roborock.com/iottest/default_avatar.png",
    }
)

MOCK_CONFIG = {
    "username": USER_EMAIL,
    "user_data": USER_DATA.as_dict(),
    "base_url": None,
}

HOME_DATA_RAW = {
    "id": 123456,
    "name": "My Home",
    "lon": None,
    "lat": None,
    "geoName": None,
    "products": [
        {
            "id": "abc123",
            "name": "Roborock S7 MaxV",
            "code": "a27",
            "model": "roborock.vacuum.a27",
            "iconUrl": None,
            "attribute": None,
            "capability": 0,
            "category": "robot.vacuum.cleaner",
            "schema": [
                {
                    "id": "101",
                    "name": "rpc_request",
                    "code": "rpc_request",
                    "mode": "rw",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "102",
                    "name": "rpc_response",
                    "code": "rpc_response",
                    "mode": "rw",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "120",
                    "name": "错误代码",
                    "code": "error_code",
                    "mode": "ro",
                    "type": "ENUM",
                    "property": '{"range": []}',
                    "desc": None,
                },
                {
                    "id": "121",
                    "name": "设备状态",
                    "code": "state",
                    "mode": "ro",
                    "type": "ENUM",
                    "property": '{"range": []}',
                    "desc": None,
                },
                {
                    "id": "122",
                    "name": "设备电量",
                    "code": "battery",
                    "mode": "ro",
                    "type": "ENUM",
                    "property": '{"range": []}',
                    "desc": None,
                },
                {
                    "id": "123",
                    "name": "清扫模式",
                    "code": "fan_power",
                    "mode": "rw",
                    "type": "ENUM",
                    "property": '{"range": []}',
                    "desc": None,
                },
                {
                    "id": "124",
                    "name": "拖地模式",
                    "code": "water_box_mode",
                    "mode": "rw",
                    "type": "ENUM",
                    "property": '{"range": []}',
                    "desc": None,
                },
                {
                    "id": "125",
                    "name": "主刷寿命",
                    "code": "main_brush_life",
                    "mode": "rw",
                    "type": "VALUE",
                    "property": '{"max": 100, "min": 0, "step": 1, "unit": null, "scale": 1}',
                    "desc": None,
                },
                {
                    "id": "126",
                    "name": "边刷寿命",
                    "code": "side_brush_life",
                    "mode": "rw",
                    "type": "VALUE",
                    "property": '{"max": 100, "min": 0, "step": 1, "unit": null, "scale": 1}',
                    "desc": None,
                },
                {
                    "id": "127",
                    "name": "滤网寿命",
                    "code": "filter_life",
                    "mode": "rw",
                    "type": "VALUE",
                    "property": '{"max": 100, "min": 0, "step": 1, "unit": null, "scale": 1}',
                    "desc": None,
                },
                {
                    "id": "128",
                    "name": "额外状态",
                    "code": "additional_props",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "130",
                    "name": "完成事件",
                    "code": "task_complete",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "131",
                    "name": "电量不足任务取消",
                    "code": "task_cancel_low_power",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "132",
                    "name": "运动中任务取消",
                    "code": "task_cancel_in_motion",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "133",
                    "name": "充电状态",
                    "code": "charge_status",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
                {
                    "id": "134",
                    "name": "烘干状态",
                    "code": "drying_status",
                    "mode": "ro",
                    "type": "RAW",
                    "property": None,
                    "desc": None,
                },
            ],
        }
    ],
    "devices": [
        {
            "duid": "abc123",
            "name": "Roborock S7 MaxV",
            "attribute": None,
            "activeTime": 1672364449,
            "localKey": "abc123",
            "runtimeEnv": None,
            "timeZoneId": "America/Los_Angeles",
            "iconUrl": "",
            "productId": "abc123",
            "lon": None,
            "lat": None,
            "share": False,
            "shareTime": None,
            "online": True,
            "fv": "02.56.02",
            "pv": "1.0",
            "roomId": 2362003,
            "tuyaUuid": None,
            "tuyaMigrated": False,
            "extra": '{"RRPhotoPrivacyVersion": "1"}',
            "sn": "abc123",
            "featureSet": "2234201184108543",
            "newFeatureSet": "0000000000002041",
            "deviceStatus": {
                "121": 8,
                "122": 100,
                "123": 102,
                "124": 203,
                "125": 94,
                "126": 90,
                "127": 87,
                "128": 0,
                "133": 1,
                "120": 0,
            },
            "silentOtaSwitch": True,
        }
    ],
    "receivedDevices": [],
    "rooms": [
        {"id": 2362048, "name": "Example room 1"},
        {"id": 2362044, "name": "Example room 2"},
        {"id": 2362041, "name": "Example room 3"},
    ],
}

HOME_DATA: HomeData = HomeData.from_dict(HOME_DATA_RAW)

CLEAN_RECORD = CleanRecord.from_dict(
    {
        "begin": 1672543330,
        "end": 1672544638,
        "duration": 1176,
        "area": 20965000,
        "error": 0,
        "complete": 1,
        "start_type": 2,
        "clean_type": 3,
        "finish_reason": 56,
        "dust_collection_status": 1,
        "avoid_count": 19,
        "wash_count": 2,
        "map_flag": 0,
    }
)

CLEAN_SUMMARY = CleanSummary.from_dict(
    {
        "clean_time": 74382,
        "clean_area": 1159182500,
        "clean_count": 31,
        "dust_collection_count": 25,
        "records": [
            1672543330,
            1672458041,
        ],
    }
)

CONSUMABLE = Consumable.from_dict(
    {
        "main_brush_work_time": 74382,
        "side_brush_work_time": 74382,
        "filter_work_time": 74382,
        "filter_element_work_time": 0,
        "sensor_dirty_time": 74382,
        "strainer_work_times": 65,
        "dust_collection_work_times": 25,
        "cleaning_brush_work_times": 65,
    }
)

DND_TIMER = DNDTimer.from_dict(
    {
        "start_hour": 22,
        "start_minute": 0,
        "end_hour": 7,
        "end_minute": 0,
        "enabled": 1,
    }
)

STATUS = Status.from_dict(
    {
        "msg_ver": 2,
        "msg_seq": 458,
        "state": 8,
        "battery": 100,
        "clean_time": 1176,
        "clean_area": 20965000,
        "error_code": 0,
        "map_present": 1,
        "in_cleaning": 0,
        "in_returning": 0,
        "in_fresh_state": 1,
        "lab_status": 1,
        "water_box_status": 1,
        "back_type": -1,
        "wash_phase": 0,
        "wash_ready": 0,
        "fan_power": 102,
        "dnd_enabled": 0,
        "map_status": 3,
        "is_locating": 0,
        "lock_status": 0,
        "water_box_mode": 203,
        "water_box_carriage_status": 1,
        "mop_forbidden_enable": 1,
        "camera_status": 3457,
        "is_exploring": 0,
        "home_sec_status": 0,
        "home_sec_enable_password": 0,
        "adbumper_status": [0, 0, 0],
        "water_shortage_status": 0,
        "dock_type": 3,
        "dust_collection_status": 0,
        "auto_dust_collection": 1,
        "avoid_count": 19,
        "mop_mode": 300,
        "debug_mode": 0,
        "collision_avoid_status": 1,
        "switch_map_mode": 0,
        "dock_error_status": 0,
        "charge_status": 1,
        "unsave_map_reason": 0,
        "unsave_map_flag": 0,
    }
)

PROP = RoborockDeviceProp(STATUS, DND_TIMER, CLEAN_SUMMARY, CONSUMABLE, CLEAN_RECORD)
