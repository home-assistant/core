"""Support for Powerview scenes from a Powerview hub."""

import asyncio

from aiohttp.client_exceptions import ServerDisconnectedError
from aiopvapi.helpers.aiorequest import PvApiConnectionError

DOMAIN = "hunterdouglas_powerview"


MANUFACTURER = "Hunter Douglas"

HUB_ADDRESS = "address"

SCENE_DATA = "sceneData"
SHADE_DATA = "shadeData"
ROOM_DATA = "roomData"
USER_DATA = "userData"

MAC_ADDRESS_IN_USERDATA = "macAddress"
SERIAL_NUMBER_IN_USERDATA = "serialNumber"
HUB_NAME = "hubName"

FIRMWARE = "firmware"
FIRMWARE_MAINPROCESSOR = "mainProcessor"
FIRMWARE_NAME = "name"
FIRMWARE_REVISION = "revision"
FIRMWARE_SUB_REVISION = "subRevision"
FIRMWARE_BUILD = "build"

DEVICE_NAME = "device_name"
DEVICE_MAC_ADDRESS = "device_mac_address"
DEVICE_SERIAL_NUMBER = "device_serial_number"
DEVICE_REVISION = "device_revision"
DEVICE_INFO = "device_info"
DEVICE_MODEL = "device_model"
DEVICE_FIRMWARE = "device_firmware"

SCENE_NAME = "name"
SCENE_ID = "id"
ROOM_ID_IN_SCENE = "roomId"

SHADE_NAME = "name"
SHADE_ID = "id"
ROOM_ID_IN_SHADE = "roomId"

ROOM_NAME = "name"
ROOM_NAME_UNICODE = "name_unicode"
ROOM_ID = "id"

SHADE_RESPONSE = "shade"
SHADE_BATTERY_LEVEL = "batteryStrength"
SHADE_BATTERY_LEVEL_MAX = 200

STATE_ATTRIBUTE_ROOM_NAME = "roomName"

PV_API = "pv_api"
PV_HUB = "pv_hub"
PV_SHADES = "pv_shades"
PV_SCENE_DATA = "pv_scene_data"
PV_SHADE_DATA = "pv_shade_data"
PV_ROOM_DATA = "pv_room_data"
COORDINATOR = "coordinator"

HUB_EXCEPTIONS = (ServerDisconnectedError, asyncio.TimeoutError, PvApiConnectionError)

LEGACY_DEVICE_SUB_REVISION = 1
LEGACY_DEVICE_REVISION = 0
LEGACY_DEVICE_BUILD = 0
LEGACY_DEVICE_MODEL = "PowerView Hub"

DEFAULT_LEGACY_MAINPROCESSOR = {
    FIRMWARE_REVISION: LEGACY_DEVICE_REVISION,
    FIRMWARE_SUB_REVISION: LEGACY_DEVICE_SUB_REVISION,
    FIRMWARE_BUILD: LEGACY_DEVICE_BUILD,
    FIRMWARE_NAME: LEGACY_DEVICE_MODEL,
}


API_PATH_FWVERSION = "api/fwversion"
