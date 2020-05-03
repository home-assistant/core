"""Mocks for the august component."""
import json
import os
import time

from august.activity import (
    ACTIVITY_ACTIONS_DOOR_OPERATION,
    ACTIVITY_ACTIONS_DOORBELL_DING,
    ACTIVITY_ACTIONS_DOORBELL_MOTION,
    ACTIVITY_ACTIONS_DOORBELL_VIEW,
    ACTIVITY_ACTIONS_LOCK_OPERATION,
    DoorbellDingActivity,
    DoorbellMotionActivity,
    DoorbellViewActivity,
    DoorOperationActivity,
    LockOperationActivity,
)
from august.authenticator import AuthenticationState
from august.doorbell import Doorbell, DoorbellDetail
from august.lock import Lock, LockDetail

from homeassistant.components.august import (
    CONF_LOGIN_METHOD,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.setup import async_setup_component

# from tests.async_mock import AsyncMock
from tests.async_mock import AsyncMock, MagicMock, PropertyMock, patch
from tests.common import load_fixture


def _mock_get_config():
    """Return a default august config."""
    return {
        DOMAIN: {
            CONF_LOGIN_METHOD: "email",
            CONF_USERNAME: "mocked_username",
            CONF_PASSWORD: "mocked_password",
        }
    }


@patch("homeassistant.components.august.gateway.ApiAsync")
@patch("homeassistant.components.august.gateway.AuthenticatorAsync.async_authenticate")
async def _mock_setup_august(hass, api_instance, authenticate_mock, api_mock):
    """Set up august integration."""
    authenticate_mock.side_effect = MagicMock(
        return_value=_mock_august_authentication("original_token", 1234)
    )
    api_mock.return_value = api_instance
    assert await async_setup_component(hass, DOMAIN, _mock_get_config())
    await hass.async_block_till_done()
    return True


async def _create_august_with_devices(
    hass, devices, api_call_side_effects=None, activities=None
):
    if api_call_side_effects is None:
        api_call_side_effects = {}

    device_data = {"doorbells": [], "locks": []}
    for device in devices:
        if isinstance(device, LockDetail):
            device_data["locks"].append(
                {"base": _mock_august_lock(device.device_id), "detail": device}
            )
        elif isinstance(device, DoorbellDetail):
            device_data["doorbells"].append(
                {"base": _mock_august_doorbell(device.device_id), "detail": device}
            )
        else:
            raise ValueError

    def _get_device_detail(device_type, device_id):
        for device in device_data[device_type]:
            if device["detail"].device_id == device_id:
                return device["detail"]
        raise ValueError

    def _get_base_devices(device_type):
        base_devices = []
        for device in device_data[device_type]:
            base_devices.append(device["base"])
        return base_devices

    def get_lock_detail_side_effect(access_token, device_id):
        return _get_device_detail("locks", device_id)

    def get_doorbell_detail_side_effect(access_token, device_id):
        return _get_device_detail("doorbells", device_id)

    def get_operable_locks_side_effect(access_token):
        return _get_base_devices("locks")

    def get_doorbells_side_effect(access_token):
        return _get_base_devices("doorbells")

    def get_house_activities_side_effect(access_token, house_id, limit=10):
        if activities is not None:
            return activities
        return []

    def lock_return_activities_side_effect(access_token, device_id):
        lock = _get_device_detail("locks", device_id)
        return [
            # There is a check to prevent out of order events
            # so we set the doorclosed & lock event in the future
            # to prevent a race condition where we reject the event
            # because it happened before the dooropen & unlock event.
            _mock_lock_operation_activity(lock, "lock", 2000),
            _mock_door_operation_activity(lock, "doorclosed", 2000),
        ]

    def unlock_return_activities_side_effect(access_token, device_id):
        lock = _get_device_detail("locks", device_id)
        return [
            _mock_lock_operation_activity(lock, "unlock", 0),
            _mock_door_operation_activity(lock, "dooropen", 0),
        ]

    if "get_lock_detail" not in api_call_side_effects:
        api_call_side_effects["get_lock_detail"] = get_lock_detail_side_effect
    if "get_doorbell_detail" not in api_call_side_effects:
        api_call_side_effects["get_doorbell_detail"] = get_doorbell_detail_side_effect
    if "get_operable_locks" not in api_call_side_effects:
        api_call_side_effects["get_operable_locks"] = get_operable_locks_side_effect
    if "get_doorbells" not in api_call_side_effects:
        api_call_side_effects["get_doorbells"] = get_doorbells_side_effect
    if "get_house_activities" not in api_call_side_effects:
        api_call_side_effects["get_house_activities"] = get_house_activities_side_effect
    if "lock_return_activities" not in api_call_side_effects:
        api_call_side_effects[
            "lock_return_activities"
        ] = lock_return_activities_side_effect
    if "unlock_return_activities" not in api_call_side_effects:
        api_call_side_effects[
            "unlock_return_activities"
        ] = unlock_return_activities_side_effect

    return await _mock_setup_august_with_api_side_effects(hass, api_call_side_effects)


async def _mock_setup_august_with_api_side_effects(hass, api_call_side_effects):
    api_instance = MagicMock(name="Api")

    if api_call_side_effects["get_lock_detail"]:
        type(api_instance).async_get_lock_detail = AsyncMock(
            side_effect=api_call_side_effects["get_lock_detail"]
        )

    if api_call_side_effects["get_operable_locks"]:
        type(api_instance).async_get_operable_locks = AsyncMock(
            side_effect=api_call_side_effects["get_operable_locks"]
        )

    if api_call_side_effects["get_doorbells"]:
        type(api_instance).async_get_doorbells = AsyncMock(
            side_effect=api_call_side_effects["get_doorbells"]
        )

    if api_call_side_effects["get_doorbell_detail"]:
        type(api_instance).async_get_doorbell_detail = AsyncMock(
            side_effect=api_call_side_effects["get_doorbell_detail"]
        )

    if api_call_side_effects["get_house_activities"]:
        type(api_instance).async_get_house_activities = AsyncMock(
            side_effect=api_call_side_effects["get_house_activities"]
        )

    if api_call_side_effects["lock_return_activities"]:
        type(api_instance).async_lock_return_activities = AsyncMock(
            side_effect=api_call_side_effects["lock_return_activities"]
        )

    if api_call_side_effects["unlock_return_activities"]:
        type(api_instance).async_unlock_return_activities = AsyncMock(
            side_effect=api_call_side_effects["unlock_return_activities"]
        )

    return await _mock_setup_august(hass, api_instance)


def _mock_august_authentication(token_text, token_timestamp):
    authentication = MagicMock(name="august.authentication")
    type(authentication).state = PropertyMock(
        return_value=AuthenticationState.AUTHENTICATED
    )
    type(authentication).access_token = PropertyMock(return_value=token_text)
    type(authentication).access_token_expires = PropertyMock(
        return_value=token_timestamp
    )
    return authentication


def _mock_august_lock(lockid="mocklockid1", houseid="mockhouseid1"):
    return Lock(lockid, _mock_august_lock_data(lockid=lockid, houseid=houseid))


def _mock_august_doorbell(deviceid="mockdeviceid1", houseid="mockhouseid1"):
    return Doorbell(
        deviceid, _mock_august_doorbell_data(deviceid=deviceid, houseid=houseid)
    )


def _mock_august_doorbell_data(deviceid="mockdeviceid1", houseid="mockhouseid1"):
    return {
        "_id": deviceid,
        "DeviceID": deviceid,
        "name": f"{deviceid} Name",
        "HouseID": houseid,
        "UserType": "owner",
        "serialNumber": "mockserial",
        "battery": 90,
        "status": "standby",
        "currentFirmwareVersion": "mockfirmware",
        "Bridge": {
            "_id": "bridgeid1",
            "firmwareVersion": "mockfirm",
            "operative": True,
        },
        "LockStatus": {"doorState": "open"},
    }


def _mock_august_lock_data(lockid="mocklockid1", houseid="mockhouseid1"):
    return {
        "_id": lockid,
        "LockID": lockid,
        "LockName": f"{lockid} Name",
        "HouseID": houseid,
        "UserType": "owner",
        "SerialNumber": "mockserial",
        "battery": 90,
        "currentFirmwareVersion": "mockfirmware",
        "Bridge": {
            "_id": "bridgeid1",
            "firmwareVersion": "mockfirm",
            "operative": True,
        },
        "LockStatus": {"doorState": "open"},
    }


async def _mock_operative_august_lock_detail(hass):
    return await _mock_lock_from_fixture(hass, "get_lock.online.json")


async def _mock_inoperative_august_lock_detail(hass):
    return await _mock_lock_from_fixture(hass, "get_lock.offline.json")


async def _mock_activities_from_fixture(hass, path):
    json_dict = await _load_json_fixture(hass, path)
    activities = []
    for activity_json in json_dict:
        activity = _activity_from_dict(activity_json)
        if activity:
            activities.append(activity)

    return activities


async def _mock_lock_from_fixture(hass, path):
    json_dict = await _load_json_fixture(hass, path)
    return LockDetail(json_dict)


async def _mock_doorbell_from_fixture(hass, path):
    json_dict = await _load_json_fixture(hass, path)
    return DoorbellDetail(json_dict)


async def _load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("august", path)
    )
    return json.loads(fixture)


async def _mock_doorsense_enabled_august_lock_detail(hass):
    return await _mock_lock_from_fixture(hass, "get_lock.online_with_doorsense.json")


async def _mock_doorsense_missing_august_lock_detail(hass):
    return await _mock_lock_from_fixture(hass, "get_lock.online_missing_doorsense.json")


def _mock_lock_operation_activity(lock, action, offset):
    return LockOperationActivity(
        {
            "dateTime": (time.time() + offset) * 1000,
            "deviceID": lock.device_id,
            "deviceType": "lock",
            "action": action,
        }
    )


def _mock_door_operation_activity(lock, action, offset):
    return DoorOperationActivity(
        {
            "dateTime": (time.time() + offset) * 1000,
            "deviceID": lock.device_id,
            "deviceType": "lock",
            "action": action,
        }
    )


def _activity_from_dict(activity_dict):
    action = activity_dict.get("action")

    activity_dict["dateTime"] = time.time() * 1000

    if action in ACTIVITY_ACTIONS_DOORBELL_DING:
        return DoorbellDingActivity(activity_dict)
    if action in ACTIVITY_ACTIONS_DOORBELL_MOTION:
        return DoorbellMotionActivity(activity_dict)
    if action in ACTIVITY_ACTIONS_DOORBELL_VIEW:
        return DoorbellViewActivity(activity_dict)
    if action in ACTIVITY_ACTIONS_LOCK_OPERATION:
        return LockOperationActivity(activity_dict)
    if action in ACTIVITY_ACTIONS_DOOR_OPERATION:
        return DoorOperationActivity(activity_dict)
    return None
