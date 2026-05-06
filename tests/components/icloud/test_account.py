"""Tests for the iCloud account."""

from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.icloud.account import IcloudAccount, IcloudDevice
from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import DEVICE, MOCK_CONFIG, USER_INFO, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_store")
def mock_store_fixture():
    """Mock the storage."""
    with patch("homeassistant.components.icloud.account.Store") as store_mock:
        store_instance = Mock(spec=Store)
        store_instance.path = "/mock/path"
        store_mock.return_value = store_instance
        yield store_instance


@pytest.fixture(name="mock_icloud_service_no_userinfo")
def mock_icloud_service_no_userinfo_fixture():
    """Mock PyiCloudService with devices as dict but no userInfo."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        mock_device = MagicMock()
        mock_device.status = iter(DEVICE)
        mock_device.user_info = None
        service_instance.devices = mock_device
        service_mock.return_value = service_instance
        yield service_instance


async def test_setup_fails_when_userinfo_missing(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service_no_userinfo: MagicMock,
) -> None:
    """Test setup fails when userInfo is missing from devices dict."""

    assert mock_icloud_service_no_userinfo is not None

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    account = IcloudAccount(
        hass,
        MOCK_CONFIG[CONF_USERNAME],
        MOCK_CONFIG[CONF_PASSWORD],
        mock_store,
        MOCK_CONFIG[CONF_WITH_FAMILY],
        MOCK_CONFIG[CONF_MAX_INTERVAL],
        MOCK_CONFIG[CONF_GPS_ACCURACY_THRESHOLD],
        config_entry,
    )

    with pytest.raises(ConfigEntryNotReady, match="No user info found"):
        account.setup()


class MockAppleDevice:
    """Mock "Apple device" which implements the .status(...) method used by the account."""

    def __init__(self, status_dict) -> None:
        """Set status."""
        self._status = status_dict

    def status(self, key):
        """Return current status."""
        return self._status

    def __getitem__(self, key):
        """Allow indexing the device itself (device[KEY]) to proxy into the raw status dict."""
        return self._status.get(key)


class MockDevicesContainer:
    """Mock devices container which is iterable and indexable returning device status dicts."""

    def __init__(self, userinfo, devices) -> None:
        """Initialize with userinfo and list of device objects."""
        self.user_info = userinfo
        self._devices = devices

    def __iter__(self):
        """Iterate returns device objects (each must have .status(...))."""
        return iter(self._devices)

    def __len__(self):
        """Return number of devices."""
        return len(self._devices)

    def __getitem__(self, idx):
        """Indexing returns device object (which must have .status(...))."""
        dev = self._devices[idx]
        if hasattr(dev, "status"):
            return dev.status(None)
        return dev


@pytest.fixture(name="mock_icloud_service")
def mock_icloud_service_fixture():
    """Mock PyiCloudService with devices container that is iterable and indexable returning status dict."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService",
    ) as service_mock:
        service_instance = MagicMock()
        device_obj = MockAppleDevice(DEVICE)
        devices_container = MockDevicesContainer(USER_INFO, [device_obj])

        service_instance.devices = devices_container
        service_instance.requires_2fa = False

        service_mock.return_value = service_instance
        yield service_instance


async def test_setup_success_with_devices(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test successful setup with devices."""

    assert mock_icloud_service is not None

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    account = IcloudAccount(
        hass,
        MOCK_CONFIG[CONF_USERNAME],
        MOCK_CONFIG[CONF_PASSWORD],
        mock_store,
        MOCK_CONFIG[CONF_WITH_FAMILY],
        MOCK_CONFIG[CONF_MAX_INTERVAL],
        MOCK_CONFIG[CONF_GPS_ACCURACY_THRESHOLD],
        config_entry,
    )

    with patch.object(account, "_schedule_next_fetch"):
        account.setup()

    assert account.api is not None
    assert account.owner_fullname == "user name"
    assert "johntravolta" in account.family_members_fullname
    assert account.family_members_fullname["johntravolta"] == "John TRAVOLTA"


# ---------------------------------------------------------------------------
# IcloudDevice.update() — stale location detection
# ---------------------------------------------------------------------------

_FETCH_INTERVAL_MIN = 30  # minutes — threshold = 30 * 60 * 1.5 = 2700 s


def _make_device(
    hass: HomeAssistant, age_seconds: float | None, is_old: bool
) -> IcloudDevice:
    """Create an IcloudDevice with a location of the given age and isOld flag."""
    mock_account = MagicMock()
    mock_account.hass = hass
    mock_account.signal_device_new = "icloud-test-device-new"
    mock_account.fetch_interval = _FETCH_INTERVAL_MIN
    mock_account.owner_fullname = "Test User"
    mock_account.family_members_fullname = {}

    ts_ms = (
        int((utcnow() - timedelta(seconds=age_seconds)).timestamp() * 1000)
        if age_seconds is not None
        else None
    )
    location = {
        "latitude": 60.1699,
        "longitude": 24.9384,
        "horizontalAccuracy": 10.0,
        "timeStamp": ts_ms,
        "isOld": is_old,
    }
    status = {**DEVICE, "location": location}
    device = IcloudDevice(mock_account, MagicMock(), dict(DEVICE))
    with patch("homeassistant.components.icloud.account.dispatcher_send"):
        device.update(status)
    return device


def test_icloud_device_clears_stale_location(hass: HomeAssistant) -> None:
    """Test that isOld=True with a timestamp older than 1.5x fetch_interval clears location.

    This is the core stale-location feature: Apple occasionally returns isOld=True
    to indicate a cached GPS fix. If that fix is older than the polling threshold,
    it is discarded so the device appears as 'unknown' rather than showing an
    outdated position.
    """
    device = _make_device(
        hass, age_seconds=3600, is_old=True
    )  # 3600s >> 2700s threshold
    assert device.location is None


def test_icloud_device_keeps_recent_location_when_is_old(hass: HomeAssistant) -> None:
    """Test that isOld=True with a recent timestamp keeps the location.

    If Apple sets isOld=True but the fix is only a minute old, it is still within
    the staleness threshold and should be accepted.
    """
    device = _make_device(hass, age_seconds=60, is_old=True)  # 60s << 2700s threshold
    assert device.location is not None


def test_icloud_device_keeps_location_when_not_is_old(hass: HomeAssistant) -> None:
    """Test that isOld=False keeps the location regardless of timestamp age.

    Only locations explicitly marked isOld=True are subject to staleness clearing.
    An old-looking timestamp alone is not sufficient to discard the fix.
    """
    device = _make_device(hass, age_seconds=3600, is_old=False)  # old but not flagged
    assert device.location is not None


def test_icloud_device_keeps_location_when_timestamp_missing(
    hass: HomeAssistant,
) -> None:
    """Test that isOld=True without a timestamp does not clear the location.

    Without a timestamp we cannot compute age_seconds, so the stale threshold
    check is skipped and the location is kept.
    """
    device = _make_device(hass, age_seconds=None, is_old=True)
    assert device.location is not None


def test_icloud_device_accepts_zero_coordinates(hass: HomeAssistant) -> None:
    """Test that latitude=0.0 and longitude=0.0 are accepted as valid coordinates.

    The old truthiness check treated 0.0 as falsy and would silently drop valid
    fixes at the equator/prime-meridian intersection. The is not None guard fixes
    this; this test prevents regressions.
    """
    mock_account = MagicMock()
    mock_account.hass = hass
    mock_account.signal_device_new = "icloud-test-device-new"
    mock_account.fetch_interval = _FETCH_INTERVAL_MIN
    mock_account.owner_fullname = "Test User"
    mock_account.family_members_fullname = {}

    ts_ms = int((utcnow() - timedelta(seconds=60)).timestamp() * 1000)
    status = {
        **DEVICE,
        "location": {
            "latitude": 0.0,
            "longitude": 0.0,
            "horizontalAccuracy": 10.0,
            "timeStamp": ts_ms,
            "isOld": False,
        },
    }
    device = IcloudDevice(mock_account, MagicMock(), dict(DEVICE))
    with patch("homeassistant.components.icloud.account.dispatcher_send"):
        device.update(status)

    assert device.location is not None
    assert device.location["latitude"] == 0.0
    assert device.location["longitude"] == 0.0


def test_icloud_device_no_location_data_does_not_set_location(
    hass: HomeAssistant,
) -> None:
    """Test that a status with no location dict leaves the device location as None."""
    mock_account = MagicMock()
    mock_account.hass = hass
    mock_account.signal_device_new = "icloud-test-device-new"
    mock_account.fetch_interval = _FETCH_INTERVAL_MIN
    mock_account.owner_fullname = "Test User"
    mock_account.family_members_fullname = {}

    status = {**DEVICE, "location": None}
    device = IcloudDevice(mock_account, MagicMock(), dict(DEVICE))
    with patch("homeassistant.components.icloud.account.dispatcher_send"):
        device.update(status)

    assert device.location is None


def test_icloud_device_stale_transition_logs_warning(
    hass: HomeAssistant,
) -> None:
    """Test that the stale-location warning fires when transitioning from a valid fix.

    The warning should only log on the transition (valid → stale), not on every
    subsequent poll while the stale fix persists.
    """
    mock_account = MagicMock()
    mock_account.hass = hass
    mock_account.signal_device_new = "icloud-test-device-new"
    mock_account.fetch_interval = _FETCH_INTERVAL_MIN
    mock_account.owner_fullname = "Test User"
    mock_account.family_members_fullname = {}

    def _make_status(age_seconds: float, is_old: bool) -> dict:
        ts_ms = int((utcnow() - timedelta(seconds=age_seconds)).timestamp() * 1000)
        return {
            **DEVICE,
            "location": {
                "latitude": 60.1699,
                "longitude": 24.9384,
                "horizontalAccuracy": 10.0,
                "timeStamp": ts_ms,
                "isOld": is_old,
            },
        }

    device = IcloudDevice(mock_account, MagicMock(), dict(DEVICE))

    with patch("homeassistant.components.icloud.account.dispatcher_send"):
        # First update: fresh fix → location is set
        device.update(_make_status(age_seconds=60, is_old=False))
    assert device.location is not None

    # Second update: stale fix → warning fires, location cleared
    with patch("homeassistant.components.icloud.account.dispatcher_send"):
        with patch("homeassistant.components.icloud.account._LOGGER") as mock_logger:
            device.update(_make_status(age_seconds=3600, is_old=True))

    assert device.location is None
    mock_logger.warning.assert_called_once()
