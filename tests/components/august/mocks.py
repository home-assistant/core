"""Mocks for the august component."""
import datetime
from unittest.mock import MagicMock, PropertyMock

from august.activity import Activity
from august.api import Api
from august.exceptions import AugustApiHTTPError
from august.lock import Lock, LockDetail

from homeassistant.components.august import AugustData
from homeassistant.components.august.binary_sensor import AugustDoorBinarySensor
from homeassistant.components.august.lock import AugustLock
from homeassistant.util import dt


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


class MockAugustComponentLock(AugustLock):
    """A mock for august component AugustLock class."""

    def _update_lock_status(self, lock_status, activity_start_time_utc):
        """Mock updating the lock status."""
        self._data.set_last_lock_status_update_time_utc(
            self._lock.device_id, activity_start_time_utc
        )
        self.last_update_lock_status = {}
        self.last_update_lock_status["lock_status"] = lock_status
        self.last_update_lock_status[
            "activity_start_time_utc"
        ] = activity_start_time_utc


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
    type(authentication).access_token = PropertyMock(return_value=token_text)
    type(authentication).access_token_expires = PropertyMock(
        return_value=token_timestamp
    )
    return authentication


def _mock_august_lock(lockid="mocklockid1", houseid="mockhouseid1"):
    return Lock(lockid, _mock_august_lock_data(lockid=lockid, houseid=houseid))


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


def _mock_doorsense_missing_august_lock_detail(lockid):
    doorsense_lock_detail_data = _mock_august_lock_data(lockid=lockid)
    del doorsense_lock_detail_data["LockStatus"]["doorState"]
    return LockDetail(doorsense_lock_detail_data)
