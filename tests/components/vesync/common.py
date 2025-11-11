"""Common methods used across tests for VeSync."""

from typing import Any

from homeassistant.components.vesync.const import DOMAIN
from homeassistant.util.json import JsonObjectType

from tests.common import load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

ENTITY_HUMIDIFIER = "humidifier.humidifier_200s"
ENTITY_HUMIDIFIER_MIST_LEVEL = "number.humidifier_200s_mist_level"
ENTITY_HUMIDIFIER_HUMIDITY = "sensor.humidifier_200s_humidity"
ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT = "select.humidifier_300s_night_light_level"

ENTITY_FAN = "fan.SmartTowerFan"

ENTITY_SWITCH_DISPLAY = "switch.humidifier_200s_display"

DEVICE_CATEGORIES = [
    "outlets",
    "switches",
    "fans",
    "bulbs",
    "humidifiers",
    "air_purifiers",
    "air_fryers",
    "thermostats",
]

ALL_DEVICES = load_json_object_fixture("vesync-devices.json", DOMAIN)
ALL_DEVICE_NAMES: list[str] = [
    dev["deviceName"] for dev in ALL_DEVICES["result"]["list"]
]
DEVICE_FIXTURES: dict[str, list[tuple[str, str, str]]] = {
    "Humidifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "humidifier-detail.json")
    ],
    "Humidifier 600S": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "humidifier-detail.json")
    ],
    "Air Purifier 131s": [
        (
            "post",
            "/cloud/v1/deviceManaged/deviceDetail",
            "air-purifier-131s-detail.json",
        )
    ],
    "Air Purifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "air-purifier-detail.json")
    ],
    "Air Purifier 400s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "air-purifier-detail.json")
    ],
    "Air Purifier 600s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "air-purifier-detail.json")
    ],
    "Dimmable Light": [
        ("post", "/cloud/v1/deviceManaged/deviceDetail", "device-detail.json")
    ],
    "Temperature Light": [
        ("post", "/cloud/v1/deviceManaged/bypass", "light-detail.json")
    ],
    "Outlet": [
        ("get", "/v1/device/outlet/detail", "outlet-detail.json"),
        ("post", "/cloud/v1/device/getLastWeekEnergy", "outlet-energy.json"),
        ("post", "/cloud/v1/device/getLastMonthEnergy", "outlet-energy.json"),
        ("post", "/cloud/v1/device/getLastYearEnergy", "outlet-energy.json"),
    ],
    "Wall Switch": [
        ("post", "/cloud/v1/deviceManaged/deviceDetail", "device-detail.json")
    ],
    "Dimmer Switch": [
        ("post", "/cloud/v1/deviceManaged/deviceDetail", "dimmer-detail.json")
    ],
    "SmartTowerFan": [("post", "/cloud/v2/deviceManaged/bypassV2", "fan-detail.json")],
}


def mock_devices_response(
    aioclient_mock: AiohttpClientMocker, device_name: str
) -> None:
    """Build a response for the Helpers.call_api method."""
    device_list = [
        device
        for device in ALL_DEVICES["result"]["list"]
        if device["deviceName"] == device_name
    ]

    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={
            "traceId": "1234",
            "code": 0,
            "msg": None,
            "module": None,
            "stacktrace": None,
            "result": {
                "total": len(device_list),
                "pageSize": len(device_list),
                "pageNo": 1,
                "list": device_list,
            },
        },
    )

    for fixture in DEVICE_FIXTURES[device_name]:
        getattr(aioclient_mock, fixture[0])(
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_json_object_fixture(fixture[2], DOMAIN),
        )


def mock_multiple_device_responses(
    aioclient_mock: AiohttpClientMocker, device_names: list[str]
) -> None:
    """Build a response for the Helpers.call_api method for multiple devices."""
    device_list = [
        device
        for device in ALL_DEVICES["result"]["list"]
        if device["deviceName"] in device_names
    ]

    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={
            "traceId": "1234",
            "code": 0,
            "msg": None,
            "module": None,
            "stacktrace": None,
            "result": {
                "total": len(device_list),
                "pageSize": len(device_list),
                "pageNo": 1,
                "list": device_list,
            },
        },
    )

    for device_name in device_names:
        fixture = DEVICE_FIXTURES[device_name][0]

        getattr(aioclient_mock, fixture[0])(
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_json_object_fixture(fixture[2], DOMAIN),
        )


def mock_air_purifier_400s_update_response(aioclient_mock: AiohttpClientMocker) -> None:
    """Build a response for the Helpers.call_api method for air_purifier_400s with updated data."""

    device_name = "Air Purifier 400s"
    for fixture in DEVICE_FIXTURES[device_name]:
        getattr(aioclient_mock, fixture[0])(
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_json_object_fixture("air-purifier-detail-updated.json", DOMAIN),
        )


def mock_device_response(
    aioclient_mock: AiohttpClientMocker, device_name: str, override: Any
) -> None:
    """Build a response for the Helpers.call_api method with updated data.

    The provided override only applies to the base device response.
    """

    def load_and_merge(source: str) -> JsonObjectType:
        json = load_json_object_fixture(source, DOMAIN)

        if override:
            json.update(override)

        return json

    fixtures = DEVICE_FIXTURES[device_name]

    # The first item contain basic device details
    if len(fixtures) > 0:
        item = fixtures[0]

        getattr(aioclient_mock, item[0])(
            f"https://smartapi.vesync.com{item[1]}",
            json=load_and_merge(item[2]),
        )


def mock_outlet_energy_response(
    aioclient_mock: AiohttpClientMocker, device_name: str, override: Any = None
) -> None:
    """Build a response for the Helpers.call_api energy request with updated data."""

    def load_and_merge(source: str) -> JsonObjectType:
        json = load_json_object_fixture(source, DOMAIN)

        if override:
            if "result" in json:
                json["result"].update(override)
            else:
                json.update(override)

        return json

    # Skip the device details (1st item)
    for fixture in DEVICE_FIXTURES[device_name][1:]:
        getattr(aioclient_mock, fixture[0])(
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_and_merge(fixture[2]),
        )
