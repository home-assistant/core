"""Tests for the iCloud account."""

from unittest.mock import MagicMock, Mock, patch

from pyicloud.exceptions import PyiCloudConnectionException
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
    """Mock Apple device implementing .status() used by the account."""

    def __init__(self, status_dict) -> None:
        """Set status."""
        self._status = status_dict

    def status(self, key):
        """Return current status."""
        return self._status

    def __getitem__(self, key):
        """Allow indexing to proxy into the raw status dict."""
        return self._status.get(key)


class MockDevicesContainer:
    """Mock devices container, iterable and indexable."""

    def __init__(self, userinfo, devices) -> None:
        """Initialize with userinfo and list of device objects."""
        self.user_info = userinfo
        self._devices = devices
        self.refresh_calls: list[bool] = []

    def refresh(self, locate: bool = False) -> None:
        """Record refresh calls made by the account."""
        self.refresh_calls.append(locate)

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
    """Mock PyiCloudService with iterable and indexable devices."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService",
    ) as service_mock:
        service_instance = MagicMock()
        device_obj = MockAppleDevice(DEVICE)
        devices_container = MockDevicesContainer(USER_INFO, [device_obj])

        service_instance.devices = devices_container
        service_instance.requires_2fa = False

        service_mock.return_value = service_instance
        yield service_mock


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test a transport failure during setup asks for a retry."""

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

    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService",
            side_effect=PyiCloudConnectionException(reason="Connection error"),
        ),
        pytest.raises(ConfigEntryNotReady) as err,
    ):
        account.setup()

    assert err.value.translation_key == "cannot_connect"


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
    # The account polls devices itself, so pyicloud's own Find My monitor is disabled.
    assert mock_icloud_service.call_args.kwargs["refresh_interval"] is None
    # The FindMyiPhoneServiceManager constructor just located every device, so
    # the first update must read that fresh data without a second active locate.
    assert mock_icloud_service.return_value.devices.refresh_calls == []
    assert "device1" in account.devices

    # Later updates request a fresh GPS fix on every poll.
    with patch.object(account, "_schedule_next_fetch"):
        account.update_devices()
    assert mock_icloud_service.return_value.devices.refresh_calls == [True]


async def test_a_failed_locate_does_not_cost_the_poll(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that the devices are still read when the locate request fails.

    Locating is best effort. iCloud still holds whichever fixes it had, and
    reading those beats leaving the account with nothing at all until the
    next poll comes round.
    """
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
    service = mock_icloud_service.return_value

    with patch.object(account, "_schedule_next_fetch"):
        await hass.async_add_executor_job(account.setup)

        # A later poll asks for a locate, and iCloud refuses it.
        service.devices.refresh = Mock(side_effect=Exception("locate failed"))
        await hass.async_add_executor_job(account.update_devices)

    service.devices.refresh.assert_called_once_with(locate=True)
    # An error ending the poll early would have left the two minute retry
    # interval in place; reading the devices recomputes it.
    assert account.fetch_interval != 2
    assert "device1" in account.devices


async def test_a_poll_with_no_devices_still_schedules_the_next_one(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that an empty device list is not indexed after a failed locate.

    Carrying on past a failed locate reaches the pending-device check with
    whatever iCloud had, which can be nothing. Indexing that ends the poll
    before it arms the next one, leaving the account stopped.
    """
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
    service = mock_icloud_service.return_value

    with patch.object(account, "_schedule_next_fetch") as schedule:
        await hass.async_add_executor_job(account.setup)
        schedule.reset_mock()

        service.devices = MockDevicesContainer(USER_INFO, [])
        service.devices.refresh = Mock(side_effect=Exception("locate failed"))
        await hass.async_add_executor_job(account.update_devices)

    schedule.assert_called_once()
