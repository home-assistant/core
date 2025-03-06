"""Mock data for Roborock tests."""

from __future__ import annotations

from PIL import Image
from roborock.containers import (
    CleanRecord,
    CleanSummary,
    Consumable,
    DnDTimer,
    HomeData,
    HomeDataScene,
    MultiMapsList,
    NetworkInfo,
    S7Status,
    UserData,
)
from roborock.roborock_typing import DeviceProp
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.map_data import ImageData
from vacuum_map_parser_roborock.map_data_parser import MapData

from homeassistant.components.roborock import CONF_BASE_URL, CONF_USER_DATA
from homeassistant.const import CONF_USERNAME

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
    CONF_USERNAME: USER_EMAIL,
    CONF_USER_DATA: USER_DATA.as_dict(),
    CONF_BASE_URL: None,
}

HOME_DATA_RAW = {
    "id": 123456,
    "name": "My Home",
    "lon": None,
    "lat": None,
    "geoName": None,
    "products": [
        {
            "id": "s7_product",
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
        },
        {
            "id": "dyad_product",
            "name": "Roborock Dyad Pro",
            "model": "roborock.wetdryvac.a56",
            "category": "roborock.wetdryvac",
            "capability": 2,
            "schema": [
                {
                    "id": "134",
                    "name": "烘干状态",
                    "code": "drying_status",
                    "mode": "ro",
                    "type": "RAW",
                },
                {
                    "id": "200",
                    "name": "启停",
                    "code": "start",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "201",
                    "name": "状态",
                    "code": "status",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "202",
                    "name": "自清洁模式",
                    "code": "self_clean_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "203",
                    "name": "自清洁强度",
                    "code": "self_clean_level",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "204",
                    "name": "烘干强度",
                    "code": "warm_level",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "205",
                    "name": "洗地模式",
                    "code": "clean_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "206",
                    "name": "吸力",
                    "code": "suction",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "207",
                    "name": "水量",
                    "code": "water_level",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "208",
                    "name": "滚刷转速",
                    "code": "brush_speed",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "209",
                    "name": "电量",
                    "code": "power",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "210",
                    "name": "预约时间",
                    "code": "countdown_time",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "212",
                    "name": "自动自清洁",
                    "code": "auto_self_clean_set",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "213",
                    "name": "自动烘干",
                    "code": "auto_dry",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "214",
                    "name": "滤网已工作时间",
                    "code": "mesh_left",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "215",
                    "name": "滚刷已工作时间",
                    "code": "brush_left",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "216",
                    "name": "错误值",
                    "code": "error",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "218",
                    "name": "滤网重置",
                    "code": "mesh_reset",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "219",
                    "name": "滚刷重置",
                    "code": "brush_reset",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "221",
                    "name": "音量",
                    "code": "volume_set",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "222",
                    "name": "直立解锁自动运行开关",
                    "code": "stand_lock_auto_run",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "223",
                    "name": "自动自清洁 - 模式",
                    "code": "auto_self_clean_set_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "224",
                    "name": "自动烘干 - 模式",
                    "code": "auto_dry_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "225",
                    "name": "静音烘干时长",
                    "code": "silent_dry_duration",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "226",
                    "name": "勿扰模式开关",
                    "code": "silent_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "227",
                    "name": "勿扰开启时间",
                    "code": "silent_mode_start_time",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "228",
                    "name": "勿扰结束时间",
                    "code": "silent_mode_end_time",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "229",
                    "name": "近30天每天洗地时长",
                    "code": "recent_run_time",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "230",
                    "name": "洗地总时长",
                    "code": "total_run_time",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "235",
                    "name": "featureinfo",
                    "code": "feature_info",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "236",
                    "name": "恢复初始设置",
                    "code": "recover_settings",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "237",
                    "name": "烘干倒计时",
                    "code": "dry_countdown",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "10000",
                    "name": "ID点数据查询",
                    "code": "id_query",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10001",
                    "name": "防串货",
                    "code": "f_c",
                    "mode": "ro",
                    "type": "STRING",
                },
                {
                    "id": "10002",
                    "name": "定时任务",
                    "code": "schedule_task",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10003",
                    "name": "语音包切换",
                    "code": "snd_switch",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10004",
                    "name": "语音包/OBA信息",
                    "code": "snd_state",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10005",
                    "name": "产品信息",
                    "code": "product_info",
                    "mode": "ro",
                    "type": "STRING",
                },
                {
                    "id": "10006",
                    "name": "隐私协议",
                    "code": "privacy_info",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10007",
                    "name": "OTA info",
                    "code": "ota_nfo",
                    "mode": "ro",
                    "type": "STRING",
                },
                {
                    "id": "10101",
                    "name": "rpc req",
                    "code": "rpc_req",
                    "mode": "wo",
                    "type": "STRING",
                },
                {
                    "id": "10102",
                    "name": "rpc resp",
                    "code": "rpc_resp",
                    "mode": "ro",
                    "type": "STRING",
                },
            ],
        },
        {
            "id": "zeo_id",
            "name": "Zeo One",
            "model": "roborock.wm.a102",
            "category": "roborock.wm",
            "capability": 2,
            "schema": [
                {
                    "id": "134",
                    "name": "烘干状态",
                    "code": "drying_status",
                    "mode": "ro",
                    "type": "RAW",
                },
                {
                    "id": "200",
                    "name": "启动",
                    "code": "start",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "201",
                    "name": "暂停",
                    "code": "pause",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "202",
                    "name": "关机",
                    "code": "shutdown",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "203",
                    "name": "状态",
                    "code": "status",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "204",
                    "name": "模式",
                    "code": "mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "205",
                    "name": "程序",
                    "code": "program",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "206",
                    "name": "童锁",
                    "code": "child_lock",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "207",
                    "name": "洗涤温度",
                    "code": "temp",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "208",
                    "name": "漂洗次数",
                    "code": "rinse_times",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "209",
                    "name": "滚筒转速",
                    "code": "spin_level",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "210",
                    "name": "干燥度",
                    "code": "drying_mode",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "211",
                    "name": "自动投放-洗衣液",
                    "code": "detergent_set",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "212",
                    "name": "自动投放-柔顺剂",
                    "code": "softener_set",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "213",
                    "name": "洗衣液投放量",
                    "code": "detergent_type",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "214",
                    "name": "柔顺剂投放量",
                    "code": "softener_type",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "217",
                    "name": "预约时间",
                    "code": "countdown",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "218",
                    "name": "洗衣剩余时间",
                    "code": "washing_left",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "219",
                    "name": "门锁状态",
                    "code": "doorlock_state",
                    "mode": "ro",
                    "type": "BOOL",
                },
                {
                    "id": "220",
                    "name": "故障",
                    "code": "error",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "221",
                    "name": "云程序设置",
                    "code": "custom_param_save",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "222",
                    "name": "云程序读取",
                    "code": "custom_param_get",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "223",
                    "name": "提示音",
                    "code": "sound_set",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "224",
                    "name": "距离上次筒自洁次数",
                    "code": "times_after_clean",
                    "mode": "ro",
                    "type": "VALUE",
                },
                {
                    "id": "225",
                    "name": "记忆洗衣偏好开关",
                    "code": "default_setting",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "226",
                    "name": "洗衣液用尽",
                    "code": "detergent_empty",
                    "mode": "ro",
                    "type": "BOOL",
                },
                {
                    "id": "227",
                    "name": "柔顺剂用尽",
                    "code": "softener_empty",
                    "mode": "ro",
                    "type": "BOOL",
                },
                {
                    "id": "229",
                    "name": "筒灯设定",
                    "code": "light_setting",
                    "mode": "rw",
                    "type": "BOOL",
                },
                {
                    "id": "230",
                    "name": "洗衣液投放量（单次）",
                    "code": "detergent_volume",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "231",
                    "name": "柔顺剂投放量（单次）",
                    "code": "softener_volume",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "232",
                    "name": "远程控制授权",
                    "code": "app_authorization",
                    "mode": "rw",
                    "type": "VALUE",
                },
                {
                    "id": "10000",
                    "name": "ID点查询",
                    "code": "id_query",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10001",
                    "name": "防串货",
                    "code": "f_c",
                    "mode": "ro",
                    "type": "STRING",
                },
                {
                    "id": "10004",
                    "name": "语音包/OBA信息",
                    "code": "snd_state",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10005",
                    "name": "产品信息",
                    "code": "product_info",
                    "mode": "ro",
                    "type": "STRING",
                },
                {
                    "id": "10006",
                    "name": "隐私协议",
                    "code": "privacy_info",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10007",
                    "name": "OTA info",
                    "code": "ota_nfo",
                    "mode": "rw",
                    "type": "STRING",
                },
                {
                    "id": "10008",
                    "name": "洗衣记录",
                    "code": "washing_log",
                    "mode": "ro",
                    "type": "BOOL",
                },
                {
                    "id": "10101",
                    "name": "rpc req",
                    "code": "rpc_req",
                    "mode": "wo",
                    "type": "STRING",
                },
                {
                    "id": "10102",
                    "name": "rpc resp",
                    "code": "rpc_resp",
                    "mode": "ro",
                    "type": "STRING",
                },
            ],
        },
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
            "productId": "s7_product",
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
        },
        {
            "duid": "device_2",
            "name": "Roborock S7 2",
            "attribute": None,
            "activeTime": 1672364449,
            "localKey": "device_2",
            "runtimeEnv": None,
            "timeZoneId": "America/Los_Angeles",
            "iconUrl": "",
            "productId": "s7_product",
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
        },
    ],
    "receivedDevices": [
        {
            "duid": "dyad_duid",
            "name": "Dyad Pro",
            "localKey": "abc",
            "fv": "01.12.34",
            "productId": "dyad_product",
            "activeTime": 1700754026,
            "timeZoneId": "Europe/Stockholm",
            "iconUrl": "",
            "share": True,
            "shareTime": 1701367095,
            "online": True,
            "pv": "A01",
            "tuyaMigrated": False,
            "deviceStatus": {
                "10002": "",
                "202": 0,
                "235": 0,
                "214": 513,
                "225": 360,
                "212": 1,
                "228": 360,
                "209": 100,
                "10001": '{"f":"t"}',
                "237": 0,
                "10007": '{"mqttOtaData":{"mqttOtaStatus":{"status":"IDLE"}}}',
                "227": 1320,
                "10005": '{"sn":"dyad_sn","ssid":"dyad_ssid","timezone":"Europe/Stockholm","posix_timezone":"CET-1CEST,M3.5.0,M10.5.0/3","ip":"1.123.12.1","mac":"b0:4a:33:33:33:33","oba":{"language":"en","name":"A.03.0291_CE","bom":"A.03.0291","location":"de","wifiplan":"EU","timezone":"CET-1CEST,M3.5.0,M10.5.0/3;Europe/Berlin","logserver":"awsde0","featureset":"0"}"}',
                "213": 1,
                "207": 4,
                "10004": '{"sid_in_use":25,"sid_version":5,"location":"de","bom":"A.03.0291","language":"en"}',
                "206": 3,
                "216": 0,
                "221": 100,
                "222": 0,
                "223": 2,
                "203": 2,
                "230": 352,
                "205": 1,
                "210": 0,
                "200": 0,
                "226": 0,
                "208": 1,
                "229": "000,000,003,000,005,000,000,000,003,000,005,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,012,003,000,000",
                "201": 3,
                "215": 513,
                "204": 1,
                "224": 1,
            },
            "silentOtaSwitch": False,
            "f": False,
        },
        {
            "duid": "zeo_duid",
            "name": "Zeo One",
            "localKey": "zeo_local_key",
            "fv": "01.00.94",
            "productId": "zeo_id",
            "activeTime": 1699964128,
            "timeZoneId": "Europe/Berlin",
            "iconUrl": "",
            "share": True,
            "shareTime": 1712763572,
            "online": True,
            "pv": "A01",
            "tuyaMigrated": False,
            "sn": "zeo_sn",
            "featureSet": "0",
            "newFeatureSet": "40",
            "deviceStatus": {
                "208": 2,
                "205": 33,
                "221": 0,
                "226": 0,
                "10001": '{"f":"t"}',
                "214": 2,
                "225": 0,
                "232": 0,
                "222": 347414,
                "206": 0,
                "200": 1,
                "219": 0,
                "223": 0,
                "220": 0,
                "201": 0,
                "202": 1,
                "10005": '{"sn":"zeo_sn","ssid":"internet","timezone":"Europe/Berlin","posix_timezone":"CET-1CEST,M3.5.0,M10.5.0/3","ip":"192.111.11.11","mac":"b0:4a:00:00:00:00","rssi":-57,"oba":{"language":"en","name":"A.03.0403_CE","bom":"A.03.0403","location":"de","wifiplan":"EU","timezone":"CET-1CEST,M3.5.0,M10.5.0/3;Europe/Berlin","logserver":"awsde0","loglevel":"4","featureset":"0"}}',
                "211": 1,
                "210": 1,
                "217": 0,
                "203": 7,
                "213": 2,
                "209": 7,
                "224": 21,
                "218": 227,
                "212": 1,
                "207": 4,
                "204": 1,
                "10007": '{"mqttOtaData":{"mqttOtaStatus":{"status":"IDLE"}}}',
                "227": 1,
            },
            "silentOtaSwitch": False,
            "f": False,
        },
    ],
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

DND_TIMER = DnDTimer.from_dict(
    {
        "start_hour": 22,
        "start_minute": 0,
        "end_hour": 7,
        "end_minute": 0,
        "enabled": 1,
    }
)

STATUS = S7Status.from_dict(
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
PROP = DeviceProp(
    status=STATUS,
    clean_summary=CLEAN_SUMMARY,
    consumable=CONSUMABLE,
    last_clean_record=CLEAN_RECORD,
)

NETWORK_INFO = NetworkInfo(
    ip="123.232.12.1", ssid="wifi", mac="ac:cc:cc:cc:cc", bssid="bssid", rssi=90
)

MULTI_MAP_LIST = MultiMapsList.from_dict(
    {
        "maxMultiMap": 4,
        "maxBakMap": 1,
        "multiMapCount": 2,
        "mapInfo": [
            {
                "mapFlag": 0,
                "addTime": 1686235489,
                "length": 8,
                "name": "Upstairs",
                "bakMaps": [{"addTime": 1673304288}],
            },
            {
                "mapFlag": 1,
                "addTime": 1697579901,
                "length": 10,
                "name": "Downstairs",
                "bakMaps": [{"addTime": 1695521431}],
            },
        ],
    }
)

MAP_DATA = MapData(0, 0)
MAP_DATA.image = ImageData(
    100, 10, 10, 10, 10, ImageConfig(), Image.new("RGB", (1, 1)), lambda p: p
)


SCENES = [
    HomeDataScene.from_dict(
        {
            "name": "sc1",
            "id": 12,
        },
    ),
    HomeDataScene.from_dict(
        {
            "name": "sc2",
            "id": 24,
        },
    ),
]
