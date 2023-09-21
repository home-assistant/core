"""Common methods used across tests for VeSync."""
import json

import requests_mock

from homeassistant.components.vesync.const import DOMAIN

from tests.common import load_fixture, load_json_object_fixture

ALL_DEVICES = load_json_object_fixture("vesync-devices.json", DOMAIN)
ALL_DEVICE_NAMES: list[str] = [
    dev["deviceName"] for dev in ALL_DEVICES["result"]["list"]
]
DEVICE_FIXTURES: dict[str, list[tuple[str, str, str]]] = {
    "Humidifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Humidifier 600S": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Air Purifier 131s": [
        ("post", "/131airPurifier/v1/device/deviceDetail", "purifier-detail.json")
    ],
    "Air Purifier 200s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
    ],
    "Air Purifier 400s": [
        ("post", "/cloud/v2/deviceManaged/bypassV2", "device-detail.json")
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
    "Outlet": [("get", "/v1/device/outlet/detail", "outlet-detail.json")],
    "Wall Switch": [
        ("post", "/inwallswitch/v1/device/devicedetail", "device-detail.json")
    ],
    "Dimmer Switch": [("post", "/dimmer/v1/device/devicedetail", "dimmer-detail.json")],
}


def mock_devices_response(
    requests_mock: requests_mock.Mocker, device_name: str
) -> None:
    """Build a response for the Helpers.call_api method."""
    device_list = []
    for device in ALL_DEVICES["result"]["list"]:
        if device["deviceName"] == device_name:
            device_list.append(device)

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


def call_api_side_effect__no_devices(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__no_devices.json", "vesync")
            ),
            200,
        )
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_humidifier(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__devices__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    elif args[0] == "/cloud/v2/deviceManaged/bypassV2" and kwargs["method"] == "post":
        return (
            json.loads(
                load_fixture(
                    "vesync_api_call__device_details__single_humidifier.json", "vesync"
                )
            ),
            200,
        )
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")


def call_api_side_effect__single_fan(*args, **kwargs):
    """Build a side_effects method for the Helpers.call_api method."""
    if args[0] == "/cloud/v1/user/login" and args[1] == "post":
        return json.loads(load_fixture("vesync_api_call__login.json", "vesync")), 200
    elif args[0] == "/cloud/v1/deviceManaged/devices" and args[1] == "post":
        return (
            json.loads(
                load_fixture("vesync_api_call__devices__single_fan.json", "vesync")
            ),
            200,
        )
    elif (
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
    else:
        raise ValueError(f"Unhandled API call args={args}, kwargs={kwargs}")
