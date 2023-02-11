"""Support for Powerview scenes from a Powerview hub."""

import asyncio

from aiohttp.client_exceptions import ServerDisconnectedError
from aiopvapi.helpers.aiorequest import PvApiConnectionError, PvApiResponseStatusError

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

REDACT_MAC_ADDRESS = "mac_address"
REDACT_SERIAL_NUMBER = "serial_number"
REDACT_HUB_ADDRESS = "hub_address"

SCENE_NAME = "name"
SCENE_ID = "id"
ROOM_ID_IN_SCENE = "roomId"

SHADE_NAME = "name"
SHADE_ID = "id"
ROOM_ID_IN_SHADE = "roomId"

ROOM_NAME = "name"
ROOM_NAME_UNICODE = "name_unicode"
ROOM_ID = "id"

SHADE_BATTERY_LEVEL = "batteryStrength"
SHADE_BATTERY_LEVEL_MAX = 200

ATTR_SIGNAL_STRENGTH = "signalStrength"
ATTR_SIGNAL_STRENGTH_MAX = 4

STATE_ATTRIBUTE_ROOM_NAME = "roomName"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    asyncio.TimeoutError,
    PvApiConnectionError,
    PvApiResponseStatusError,
)

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

POS_KIND_NONE = 0
POS_KIND_PRIMARY = 1
POS_KIND_SECONDARY = 2
POS_KIND_VANE = 3
POS_KIND_ERROR = 4


ATTR_BATTERY_KIND = "batteryKind"
BATTERY_KIND_HARDWIRED = 1
BATTERY_KIND_BATTERY = 2
BATTERY_KIND_RECHARGABLE = 3

POWER_SUPPLY_TYPE_MAP = {
    BATTERY_KIND_HARDWIRED: "Hardwired Power Supply",
    BATTERY_KIND_BATTERY: "Battery Wand",
    BATTERY_KIND_RECHARGABLE: "Rechargeable Battery",
}
POWER_SUPPLY_TYPE_REVERSE_MAP = {v: k for k, v in POWER_SUPPLY_TYPE_MAP.items()}
