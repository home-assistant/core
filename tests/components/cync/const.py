"""Test constants used in Cync tests."""

import time

import pycync
from pycync import CyncGroup, CyncHome, CyncLight, CyncRoom

MOCKED_USER = pycync.User(
    "test_token",
    "test_refresh_token",
    "test_authorize_string",
    123456789,
    expires_at=(time.time() * 1000) + 3600000,
)
MOCKED_EMAIL = "test@testuser.com"

MAIN_HOME = CyncHome(name="My Home", home_id=1000, rooms=[], global_devices=[])

ONLINE_WIFI_CONNECTED_LIGHT = CyncLight(
    device_info={
        "is_online": True,
        "id": 1101,
        "mac": "ABCDEF123456",
        "product_id": 137,
        "authorize_code": "abcd_code",
    },
    mesh_device_info={
        "deviceID": 10001,
        "displayName": "Bedroom Lamp",
        "deviceType": 137,
    },
    parent_home=MAIN_HOME,
    command_client=None,
    wifi_connected=True,
)

ONLINE_WIFI_DISCONNECTED_LIGHT = CyncLight(
    device_info={
        "is_online": True,
        "id": 1111,
        "mac": "654321ABCDEF",
        "product_id": 137,
        "authorize_code": "abcd_code",
    },
    mesh_device_info={
        "deviceID": 10002,
        "displayName": "Lamp Bulb 1",
        "deviceType": 137,
    },
    parent_home=MAIN_HOME,
    command_client=None,
    wifi_connected=False,
)

OFFLINE_WIFI_DISCONNECTED_LIGHT = CyncLight(
    device_info={
        "is_online": False,
        "id": 1112,
        "mac": "FEDCBA654321",
        "product_id": 137,
        "authorize_code": "abcd_code",
    },
    mesh_device_info={
        "deviceID": 10003,
        "displayName": "Lamp Bulb 2",
        "deviceType": 137,
    },
    parent_home=MAIN_HOME,
    command_client=None,
    wifi_connected=False,
)

LAMP_DEVICE_GROUP = CyncGroup(
    name="Office Lamp",
    group_id=1110,
    parent_home=MAIN_HOME,
    devices=[ONLINE_WIFI_DISCONNECTED_LIGHT, OFFLINE_WIFI_DISCONNECTED_LIGHT],
    command_client=None,
)

OFFICE_ROOM = CyncRoom(
    name="Office",
    room_id=1200,
    parent_home=MAIN_HOME,
    groups=[LAMP_DEVICE_GROUP],
    devices=[],
    command_client=None,
)

BEDROOM_ROOM = CyncRoom(
    name="Bedroom",
    room_id=1100,
    parent_home=MAIN_HOME,
    groups=[],
    devices=[ONLINE_WIFI_CONNECTED_LIGHT],
    command_client=None,
)
