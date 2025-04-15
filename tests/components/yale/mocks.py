"""Mocks for the yale component."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
import json
import os
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from yalexs.activity import (
    ACTIVITY_ACTIONS_BRIDGE_OPERATION,
    ACTIVITY_ACTIONS_DOOR_OPERATION,
    ACTIVITY_ACTIONS_DOORBELL_DING,
    ACTIVITY_ACTIONS_DOORBELL_MOTION,
    ACTIVITY_ACTIONS_DOORBELL_VIEW,
    ACTIVITY_ACTIONS_LOCK_OPERATION,
    SOURCE_LOCK_OPERATE,
    SOURCE_LOG,
    Activity,
    BridgeOperationActivity,
    DoorbellDingActivity,
    DoorbellMotionActivity,
    DoorbellViewActivity,
    DoorOperationActivity,
    LockOperationActivity,
)
from yalexs.api_async import ApiAsync
from yalexs.authenticator_common import Authentication, AuthenticationState
from yalexs.const import Brand
from yalexs.doorbell import Doorbell, DoorbellDetail
from yalexs.lock import Lock, LockDetail
from yalexs.manager.ratelimit import _RateLimitChecker
from yalexs.manager.socketio import SocketIORunner

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.yale.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

USER_ID = "a76c25e5-49aa-4c14-cd0c-48a6931e2081"


def _mock_get_config(
    brand: Brand = Brand.YALE_GLOBAL, jwt: str | None = None
) -> dict[str, Any]:
    """Return a default yale config."""
    return {
        DOMAIN: {
            "auth_implementation": "yale",
            "token": {
                "access_token": jwt or "access_token",
                "expires_in": 1,
                "refresh_token": "refresh_token",
                "expires_at": time.time() + 3600,
                "service": "yale",
            },
        }
    }


def _mock_authenticator(auth_state: AuthenticationState) -> Authentication:
    """Mock an yale authenticator."""
    authenticator = MagicMock()
    type(authenticator).state = PropertyMock(return_value=auth_state)
    return authenticator


def _timetoken() -> str:
    return str(time.time_ns())[:-2]


async def mock_yale_config_entry(
    hass: HomeAssistant,
) -> MockConfigEntry:
    """Mock yale config entry and client credentials."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    return entry


def mock_config_entry(jwt: str | None = None) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config(jwt=jwt)[DOMAIN],
        options={},
        unique_id=USER_ID,
    )


async def mock_client_credentials(hass: HomeAssistant) -> ClientCredential:
    """Mock client credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("1", "2"),
        DOMAIN,
    )


@contextmanager
def patch_yale_setup():
    """Patch yale setup process."""
    with (
        patch("yalexs.manager.gateway.ApiAsync") as api_mock,
        patch.object(_RateLimitChecker, "register_wakeup") as authenticate_mock,
        patch("yalexs.manager.data.SocketIORunner") as socketio_mock,
        patch.object(socketio_mock, "run"),
        patch(
            "homeassistant.components.yale.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
    ):
        yield api_mock, authenticate_mock, socketio_mock


async def _mock_setup_yale(
    hass: HomeAssistant,
    api_instance: ApiAsync,
    socketio_mock: SocketIORunner,
    authenticate_side_effect: MagicMock,
) -> ConfigEntry:
    """Set up yale integration."""
    entry = await mock_yale_config_entry(hass)
    with patch_yale_setup() as patched_setup:
        api_mock, authenticate_mock, sockio_mock_ = patched_setup
        authenticate_mock.side_effect = authenticate_side_effect
        sockio_mock_.return_value = socketio_mock
        api_mock.return_value = api_instance
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _create_yale_with_devices(
    hass: HomeAssistant,
    devices: Iterable[LockDetail | DoorbellDetail] | None = None,
    api_call_side_effects: dict[str, Any] | None = None,
    activities: list[Any] | None = None,
    brand: Brand = Brand.YALE_GLOBAL,
    authenticate_side_effect: MagicMock | None = None,
) -> tuple[ConfigEntry, SocketIORunner]:
    entry, _, socketio = await _create_yale_api_with_devices(
        hass,
        devices,
        api_call_side_effects,
        activities,
        brand,
        authenticate_side_effect,
    )
    return entry, socketio


async def _create_yale_api_with_devices(
    hass: HomeAssistant,
    devices: Iterable[LockDetail | DoorbellDetail] | None = None,
    api_call_side_effects: dict[str, Any] | None = None,
    activities: dict[str, Any] | None = None,
    brand: Brand = Brand.YALE_GLOBAL,
    authenticate_side_effect: MagicMock | None = None,
) -> tuple[ConfigEntry, ApiAsync, SocketIORunner]:
    if api_call_side_effects is None:
        api_call_side_effects = {}
    if devices is None:
        devices = ()

    update_api_call_side_effects(api_call_side_effects, devices, activities)

    api_instance = await make_mock_api(api_call_side_effects, brand)
    socketio = SocketIORunner(
        MagicMock(
            api=api_instance, async_get_access_token=AsyncMock(return_value="token")
        )
    )
    socketio.run = AsyncMock()

    entry = await _mock_setup_yale(
        hass,
        api_instance,
        socketio,
        authenticate_side_effect=authenticate_side_effect,
    )

    return entry, api_instance, socketio


def update_api_call_side_effects(
    api_call_side_effects: dict[str, Any],
    devices: Iterable[LockDetail | DoorbellDetail],
    activities: dict[str, Any] | None = None,
) -> None:
    """Update side effects dict from devices and activities."""

    device_data = {"doorbells": [], "locks": []}
    for device in devices or ():
        if isinstance(device, LockDetail):
            device_data["locks"].append(
                {"base": _mock_yale_lock(device.device_id), "detail": device}
            )
        elif isinstance(device, DoorbellDetail):
            device_data["doorbells"].append(
                {
                    "base": _mock_yale_doorbell(
                        deviceid=device.device_id,
                        brand=device._data.get("brand", Brand.YALE_GLOBAL),
                    ),
                    "detail": device,
                }
            )
        else:
            raise ValueError  # noqa: TRY004

    def _get_device_detail(device_type, device_id):
        for device in device_data[device_type]:
            if device["detail"].device_id == device_id:
                return device["detail"]
        raise ValueError

    def _get_base_devices(device_type):
        return [device["base"] for device in device_data[device_type]]

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

    api_call_side_effects.setdefault("get_lock_detail", get_lock_detail_side_effect)
    api_call_side_effects.setdefault(
        "get_doorbell_detail", get_doorbell_detail_side_effect
    )
    api_call_side_effects.setdefault(
        "get_operable_locks", get_operable_locks_side_effect
    )
    api_call_side_effects.setdefault("get_doorbells", get_doorbells_side_effect)
    api_call_side_effects.setdefault(
        "get_house_activities", get_house_activities_side_effect
    )
    api_call_side_effects.setdefault(
        "lock_return_activities", lock_return_activities_side_effect
    )
    api_call_side_effects.setdefault(
        "unlock_return_activities", unlock_return_activities_side_effect
    )
    api_call_side_effects.setdefault(
        "async_unlatch_return_activities", unlock_return_activities_side_effect
    )


async def make_mock_api(
    api_call_side_effects: dict[str, Any],
    brand: Brand = Brand.YALE_GLOBAL,
) -> ApiAsync:
    """Make a mock ApiAsync instance."""
    api_instance = MagicMock(name="Api", brand=brand)

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

    if api_call_side_effects["async_unlatch_return_activities"]:
        type(api_instance).async_unlatch_return_activities = AsyncMock(
            side_effect=api_call_side_effects["async_unlatch_return_activities"]
        )

    api_instance.async_unlock_async = AsyncMock()
    api_instance.async_lock_async = AsyncMock()
    api_instance.async_status_async = AsyncMock()
    api_instance.async_get_user = AsyncMock(return_value={"UserID": "abc"})
    api_instance.async_unlatch_async = AsyncMock()
    api_instance.async_unlatch = AsyncMock()
    api_instance.async_add_websocket_subscription = AsyncMock()

    return api_instance


def _mock_yale_authentication(
    token_text: str, token_timestamp: float, state: AuthenticationState
) -> Authentication:
    authentication = MagicMock(name="yalexs.authentication")
    type(authentication).state = PropertyMock(return_value=state)
    type(authentication).access_token = PropertyMock(return_value=token_text)
    type(authentication).access_token_expires = PropertyMock(
        return_value=token_timestamp
    )
    return authentication


def _mock_yale_lock(lockid: str = "mocklockid1", houseid: str = "mockhouseid1") -> Lock:
    return Lock(lockid, _mock_yale_lock_data(lockid=lockid, houseid=houseid))


def _mock_yale_doorbell(
    deviceid="mockdeviceid1", houseid="mockhouseid1", brand=Brand.YALE_GLOBAL
) -> Doorbell:
    return Doorbell(
        deviceid,
        _mock_yale_doorbell_data(deviceid=deviceid, houseid=houseid, brand=brand),
    )


def _mock_yale_doorbell_data(
    deviceid: str = "mockdeviceid1",
    houseid: str = "mockhouseid1",
    brand: Brand = Brand.YALE_GLOBAL,
) -> dict[str, Any]:
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


def _mock_yale_lock_data(
    lockid: str = "mocklockid1", houseid: str = "mockhouseid1"
) -> dict[str, Any]:
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


async def _mock_operative_yale_lock_detail(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.online.json")


async def _mock_lock_with_offline_key(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.online_with_keys.json")


async def _mock_inoperative_yale_lock_detail(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.offline.json")


async def _mock_activities_from_fixture(
    hass: HomeAssistant, path: str
) -> list[Activity]:
    json_dict = await _load_json_fixture(hass, path)
    activities = []
    for activity_json in json_dict:
        activity = _activity_from_dict(activity_json)
        if activity:
            activities.append(activity)

    return activities


async def _mock_lock_from_fixture(hass: HomeAssistant, path: str) -> LockDetail:
    json_dict = await _load_json_fixture(hass, path)
    return LockDetail(json_dict)


async def _mock_doorbell_from_fixture(hass: HomeAssistant, path: str) -> LockDetail:
    json_dict = await _load_json_fixture(hass, path)
    return DoorbellDetail(json_dict)


async def _load_json_fixture(hass: HomeAssistant, path: str) -> dict[str, Any]:
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("yale", path)
    )
    return json.loads(fixture)


async def _mock_doorsense_enabled_yale_lock_detail(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.online_with_doorsense.json")


async def _mock_doorsense_missing_yale_lock_detail(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.online_missing_doorsense.json")


async def _mock_lock_with_unlatch(hass: HomeAssistant) -> LockDetail:
    return await _mock_lock_from_fixture(hass, "get_lock.online_with_unlatch.json")


def _mock_lock_operation_activity(
    lock: Lock, action: str, offset: float
) -> LockOperationActivity:
    return LockOperationActivity(
        SOURCE_LOCK_OPERATE,
        {
            "dateTime": (time.time() + offset) * 1000,
            "deviceID": lock.device_id,
            "deviceType": "lock",
            "action": action,
        },
    )


def _mock_door_operation_activity(
    lock: Lock, action: str, offset: float
) -> DoorOperationActivity:
    return DoorOperationActivity(
        SOURCE_LOCK_OPERATE,
        {
            "dateTime": (time.time() + offset) * 1000,
            "deviceID": lock.device_id,
            "deviceType": "lock",
            "action": action,
        },
    )


def _activity_from_dict(activity_dict: dict[str, Any]) -> Activity | None:
    action = activity_dict.get("action")

    activity_dict["dateTime"] = time.time() * 1000

    if action in ACTIVITY_ACTIONS_DOORBELL_DING:
        return DoorbellDingActivity(SOURCE_LOG, activity_dict)
    if action in ACTIVITY_ACTIONS_DOORBELL_MOTION:
        return DoorbellMotionActivity(SOURCE_LOG, activity_dict)
    if action in ACTIVITY_ACTIONS_DOORBELL_VIEW:
        return DoorbellViewActivity(SOURCE_LOG, activity_dict)
    if action in ACTIVITY_ACTIONS_LOCK_OPERATION:
        return LockOperationActivity(SOURCE_LOG, activity_dict)
    if action in ACTIVITY_ACTIONS_DOOR_OPERATION:
        return DoorOperationActivity(SOURCE_LOG, activity_dict)
    if action in ACTIVITY_ACTIONS_BRIDGE_OPERATION:
        return BridgeOperationActivity(SOURCE_LOG, activity_dict)
    return None
