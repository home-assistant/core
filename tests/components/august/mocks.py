"""Mocks for the august component."""
import datetime
import json
import os
from unittest.mock import MagicMock, PropertyMock

from asynctest import mock
from august.activity import Activity
from august.api import Api
from august.authenticator import AuthenticationState
from august.doorbell import Doorbell, DoorbellDetail
from august.exceptions import AugustApiHTTPError
from august.lock import Lock, LockDetail, LockStatus

from homeassistant.components.august import (
    CONF_LOGIN_METHOD,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    AugustData,
)
from homeassistant.components.august.binary_sensor import AugustDoorBinarySensor
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

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


@mock.patch("homeassistant.components.august.Api")
@mock.patch("homeassistant.components.august.Authenticator.authenticate")
async def _mock_setup_august(hass, api_mocks_callback, authenticate_mock, api_mock):
    """Set up august integration."""
    authenticate_mock.side_effect = MagicMock(
        return_value=_mock_august_authentication("original_token", 1234)
    )
    api_mocks_callback(api_mock)
    assert await async_setup_component(hass, DOMAIN, _mock_get_config())
    await hass.async_block_till_done()
    return True


async def _create_august_with_devices(hass, lock_details=[], doorbell_details=[]):
    locks = []
    doorbells = []
    for lock in lock_details:
        if isinstance(lock, LockDetail):
            locks.append(_mock_august_lock(lock.device_id))
    for doorbell in doorbell_details:
        if isinstance(lock, DoorbellDetail):
            doorbells.append(_mock_august_doorbell(doorbell.device_id))

    def api_mocks_callback(api):
        def get_lock_detail_side_effect(access_token, device_id):
            for lock in lock_details:
                if isinstance(lock, LockDetail) and lock.device_id == device_id:
                    return lock

        api_instance = MagicMock()
        api_instance.get_lock_detail.side_effect = get_lock_detail_side_effect
        api_instance.get_operable_locks.return_value = locks
        api_instance.get_doorbells.return_value = doorbells
        api_instance.lock.return_value = LockStatus.LOCKED
        api_instance.unlock.return_value = LockStatus.UNLOCKED
        api.return_value = api_instance

    await _mock_setup_august(hass, api_mocks_callback)

    return True


class MockAugustApiFailing(Api):
    """A mock for py-august Api class that always has an AugustApiHTTPError."""

    def _call_api(self, *args, **kwargs):
        """Mock the time activity started."""
        raise AugustApiHTTPError("This should bubble up as its user consumable")


class MockActivity(Activity):
    """A mock for py-august Activity class."""

    def __init__(
        self, action=None, activity_start_timestamp=None, activity_end_timestamp=None
    ):
        """Init the py-august Activity class mock."""
        self._action = action
        self._activity_start_timestamp = activity_start_timestamp
        self._activity_end_timestamp = activity_end_timestamp

    @property
    def activity_start_time(self):
        """Mock the time activity started."""
        return datetime.datetime.fromtimestamp(self._activity_start_timestamp)

    @property
    def activity_end_time(self):
        """Mock the time activity ended."""
        return datetime.datetime.fromtimestamp(self._activity_end_timestamp)

    @property
    def action(self):
        """Mock the action."""
        return self._action


class MockAugustComponentDoorBinarySensor(AugustDoorBinarySensor):
    """A mock for august component AugustDoorBinarySensor class."""

    def _update_door_state(self, door_state, activity_start_time_utc):
        """Mock updating the lock status."""
        self._data.set_last_door_state_update_time_utc(
            self._door.device_id, activity_start_time_utc
        )
        self.last_update_door_state = {}
        self.last_update_door_state["door_state"] = door_state
        self.last_update_door_state["activity_start_time_utc"] = activity_start_time_utc


class MockAugustComponentData(AugustData):
    """A wrapper to mock AugustData."""

    # AugustData support multiple locks, however for the purposes of
    # mocking we currently only mock one lockid

    def __init__(
        self,
        last_lock_status_update_timestamp=1,
        last_door_state_update_timestamp=1,
        api=MockAugustApiFailing(),
        access_token="mocked_access_token",
        locks=[],
        doorbells=[],
    ):
        """Mock AugustData."""
        self._last_lock_status_update_time_utc = dt.as_utc(
            datetime.datetime.fromtimestamp(last_lock_status_update_timestamp)
        )
        self._last_door_state_update_time_utc = dt.as_utc(
            datetime.datetime.fromtimestamp(last_lock_status_update_timestamp)
        )
        self._api = api
        self._access_token = access_token
        self._locks = locks
        self._doorbells = doorbells
        self._lock_status_by_id = {}
        self._lock_last_status_update_time_utc_by_id = {}

    def set_mocked_locks(self, locks):
        """Set lock mocks."""
        self._locks = locks

    def set_mocked_doorbells(self, doorbells):
        """Set doorbell mocks."""
        self._doorbells = doorbells

    def get_last_lock_status_update_time_utc(self, device_id):
        """Mock to get last lock status update time."""
        return self._last_lock_status_update_time_utc

    def set_last_lock_status_update_time_utc(self, device_id, update_time):
        """Mock to set last lock status update time."""
        self._last_lock_status_update_time_utc = update_time

    def get_last_door_state_update_time_utc(self, device_id):
        """Mock to get last door state update time."""
        return self._last_door_state_update_time_utc

    def set_last_door_state_update_time_utc(self, device_id, update_time):
        """Mock to set last door state update time."""
        self._last_door_state_update_time_utc = update_time


def _mock_august_authenticator():
    authenticator = MagicMock(name="august.authenticator")
    authenticator.should_refresh = MagicMock(
        name="august.authenticator.should_refresh", return_value=0
    )
    authenticator.refresh_access_token = MagicMock(
        name="august.authenticator.refresh_access_token"
    )
    return authenticator


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
        deviceid, _mock_august_doorbell_data(device=deviceid, houseid=houseid)
    )


def _mock_august_doorbell_data(deviceid="mockdeviceid1", houseid="mockhouseid1"):
    return {
        "_id": deviceid,
        "DeviceID": deviceid,
        "DeviceName": deviceid + " Name",
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


def _mock_august_lock_data(lockid="mocklockid1", houseid="mockhouseid1"):
    return {
        "_id": lockid,
        "LockID": lockid,
        "LockName": lockid + " Name",
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


def _mock_operative_august_lock_detail(lockid):
    operative_lock_detail_data = _mock_august_lock_data(lockid=lockid)
    return LockDetail(operative_lock_detail_data)


def _mock_inoperative_august_lock_detail(lockid):
    inoperative_lock_detail_data = _mock_august_lock_data(lockid=lockid)
    del inoperative_lock_detail_data["Bridge"]
    return LockDetail(inoperative_lock_detail_data)


def _mock_doorsense_enabled_august_lock_detail(lockid):
    doorsense_lock_detail_data = _mock_august_lock_data(lockid=lockid)
    return LockDetail(doorsense_lock_detail_data)


async def _mock_lock_from_fixture(hass, path):
    json_dict = await _load_json_fixture(hass, path)
    return LockDetail(json_dict)


async def _load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("august", path)
    )
    return json.loads(fixture)


def _mock_doorsense_missing_august_lock_detail(lockid):
    doorsense_lock_detail_data = _mock_august_lock_data(lockid=lockid)
    del doorsense_lock_detail_data["LockStatus"]["doorState"]
    return LockDetail(doorsense_lock_detail_data)
