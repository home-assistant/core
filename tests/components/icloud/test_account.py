"""Tests for the iCloud account."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.icloud.account import IcloudAccount
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
from pyicloud.exceptions import PyiCloudAuthRequiredException, PyiCloudFailedLoginException

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


def _make_account(hass: HomeAssistant, mock_store: Mock) -> IcloudAccount:
    """Build an IcloudAccount with mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)
    return IcloudAccount(
        hass,
        MOCK_CONFIG[CONF_USERNAME],
        MOCK_CONFIG[CONF_PASSWORD],
        mock_store,
        MOCK_CONFIG[CONF_WITH_FAMILY],
        MOCK_CONFIG[CONF_MAX_INTERVAL],
        MOCK_CONFIG[CONF_GPS_ACCURACY_THRESHOLD],
        config_entry,
    )


async def test_setup_failed_login_with_2fa_logs_warning(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test setup logs a warning (not error) when the login failure is due to 2FA.

    When requires_2fa is True, the code internally raises PyiCloudFailedLoginException.
    The handler should log a warning directing the user to enter a code, not an error
    telling them their password no longer works.
    """
    account = _make_account(hass, mock_store)

    service_instance = MagicMock()
    service_instance.requires_2fa = True

    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService",
            return_value=service_instance,
        ),
        patch.object(account, "_require_reauth") as mock_reauth,
        patch("homeassistant.components.icloud.account._LOGGER") as mock_logger,
    ):
        account.setup()

    mock_reauth.assert_called_once()
    assert account.api is None
    mock_logger.warning.assert_called_once()
    mock_logger.error.assert_not_called()


async def test_setup_auth_required_exception_calls_reauth(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test setup handles PyiCloudAuthRequiredException by calling reauth.

    This covers the case where FMIP requires re-authentication even after the
    main iCloud login succeeded (e.g. MFA required specifically for Find My).
    Before this fix, the exception was unhandled and crashed setup.
    """
    account = _make_account(hass, mock_store)

    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService",
            side_effect=PyiCloudAuthRequiredException("Auth required"),
        ),
        patch.object(account, "_require_reauth") as mock_reauth,
    ):
        account.setup()

    mock_reauth.assert_called_once()
    assert account.api is None
