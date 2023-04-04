"""Common methods used across tests for VeSync."""
import json

from tests.common import load_fixture


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
