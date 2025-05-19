"""Common methods used across tests for VeSync."""

import json
from typing import Any

import requests_mock

from homeassistant.components.vesync.const import DOMAIN
from homeassistant.util.json import JsonObjectType

from tests.common import load_fixture, load_json_object_fixture

ENTITY_HUMIDIFIER = "humidifier.humidifier_200s"
ENTITY_HUMIDIFIER_MIST_LEVEL = "number.humidifier_200s_mist_level"
ENTITY_HUMIDIFIER_HUMIDITY = "sensor.humidifier_200s_humidity"
ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT = "select.humidifier_300s_night_light_level"

ENTITY_FAN = "fan.SmartTowerFan"

ENTITY_SWITCH_DISPLAY = "switch.humidifier_200s_display"

ALL_DEVICES = load_json_object_fixture("vesync-devices.json", DOMAIN)
ALL_DEVICE_NAMES: list[str] = [
    dev["deviceName"] for dev in ALL_DEVICES["result"]["list"]
]
DEVICE_FIXTURES: dict[str, list[tuple[str, str, str]]] = {
    "Humidifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "humidifier-200s.json")
    ],
    "Humidifier 600S": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Air Purifier 131s": [
        (
            "post",
            "/131airPurifier/v1/device/deviceDetail",
            "air-purifier-131s-detail.json",
        )
    ],
    "Air Purifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Air Purifier 400s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "air-purifier-400s-detail.json")
    ],
    "Air Purifier 600s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Dimmable Light": [
        ("post", "/SmartBulb/v1/device/devicedetail", "device-detail.json")
    ],
    "Temperature Light": [
        ("post", "/cloud/v1/deviceManaged/bypass", "device-detail.json")
    ],
    "Outlet": [
        ("get", "/v1/device/outlet/detail", "outlet-detail.json"),
        ("get", "/v1/device/outlet/energy/week", "outlet-energy-week.json"),
    ],
    "Wall Switch": [
        ("post", "/inwallswitch/v1/device/devicedetail", "device-detail.json")
    ],
    "Dimmer Switch": [("post", "/dimmer/v1/device/devicedetail", "dimmer-detail.json")],
    "SmartTowerFan": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "SmartTowerFan-detail.json")
    ],
}


def mock_devices_response(
    requests_mock: requests_mock.Mocker, device_name: str
) -> None:
    """Build a response for the Helpers.call_api method."""
    device_list = [
        device
        for device in ALL_DEVICES["result"]["list"]
        if device["deviceName"] == device_name
    ]

    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={"code": 0, "result": {"list": device_list}},
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/user/login",
        json=load_json_object_fixture("vesync-login.json", DOMAIN),
    )
    for fixture in DEVICE_FIXTURES[device_name]:
        requests_mock.request(
            fixture[0],
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_json_object_fixture(fixture[2], DOMAIN),
        )


def mock_multiple_device_responses(
    requests_mock: requests_mock.Mocker, device_names: list[str]
) -> None:
    """Build a response for the Helpers.call_api method for multiple devices."""
    device_list = [
        device
        for device in ALL_DEVICES["result"]["list"]
        if device["deviceName"] in device_names
    ]

    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={"code": 0, "result": {"list": device_list}},
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/user/login",
        json=load_json_object_fixture("vesync-login.json", DOMAIN),
    )
    for device_name in device_names:
        for fixture in DEVICE_FIXTURES[device_name]:
            requests_mock.request(
                fixture[0],
                f"https://smartapi.vesync.com{fixture[1]}",
                json=load_json_object_fixture(fixture[2], DOMAIN),
            )


def mock_air_purifier_400s_update_response(requests_mock: requests_mock.Mocker) -> None:
    """Build a response for the Helpers.call_api method for air_purifier_400s with updated data."""

    device_name = "Air Purifier 400s"
    for fixture in DEVICE_FIXTURES[device_name]:
        requests_mock.request(
            fixture[0],
            f"https://smartapi.vesync.com{fixture[1]}",
            json=load_json_object_fixture(
                "air-purifier-400s-detail-updated.json", DOMAIN
            ),
        )


def mock_device_response(
    requests_mock: requests_mock.Mocker, device_name: str, override: Any
) -> None:
    """Build a response for the Helpers.call_api method with updated data."""

    def load_and_merge(source: str) -> JsonObjectType:
        json = load_json_object_fixture(source, DOMAIN)

        if override:
            json.update(override)

        return json

    fixtures = DEVICE_FIXTURES[device_name]

    # The first item contain basic device details
    if len(fixtures) > 0:
        item = fixtures[0]

        requests_mock.request(
            item[0],
            f"https://smartapi.vesync.com{item[1]}",
            json=load_and_merge(item[2]),
        )


def mock_outlet_energy_response(
    requests_mock: requests_mock.Mocker, device_name: str, override: Any
) -> None:
    """Build a response for the Helpers.call_api energy request with updated data."""

    def load_and_merge(source: str) -> JsonObjectType:
        json = load_json_object_fixture(source, DOMAIN)

        if override:
            json.update(override)

        return json

    fixtures = DEVICE_FIXTURES[device_name]

    # The 2nd item contain energy details
    if len(fixtures) > 1:
        item = fixtures[1]

        requests_mock.request(
            item[0],
            f"https://smartapi.vesync.com{item[1]}",
            json=load_and_merge(item[2]),
        )


def call_api_side_effect__no_devices(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    if args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__no_devices.json", "vesync")
            ),
            200,
        )
    raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_humidifier(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    if args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__devices__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    if args[0] == "/cloud/v2/deviceManaged/bypassV2" and kwargs["method"] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__device_details__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_fan(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    if args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__single_fan.json", "vesync")
            ),
            200,
        )
    if (
        args[0] == "/131airPurifier/v1/device/deviceDetail"
        and kwargs["method"] == "post"
    ):
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__device_details__single_fan.json", "vesync"
                )
            ),
            200,
        )
    raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")
