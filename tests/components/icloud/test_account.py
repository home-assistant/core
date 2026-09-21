"""Tests for the iCloud account."""

from typing import Any
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

from .const import (
    DEVICE,
    DEVICE_WITHOUT_BATTERY,
    DEVICE_WITHOUT_LOCATION,
    LOCATION,
    MOCK_CONFIG,
    USER_INFO,
    USERNAME,
)

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
        # As the integration does. _determine_interval reaches the state
        # machine through run_callback_threadsafe, which refuses to run on
        # the event loop.
        await hass.async_add_executor_job(account.setup)

    assert account.api is not None
    assert account.owner_fullname == "user name"
    assert "johntravolta" in account.family_members_fullname
    assert account.family_members_fullname["johntravolta"] == "John TRAVOLTA"
    # An active locate must be requested on every poll (pyicloud >= 2.3.0
    # only locates at service creation, so the account has to ask for it)
    assert mock_icloud_service.devices.refresh_calls == [True]
    assert "device1" in account.devices


def _build_account(hass: HomeAssistant, mock_store: Mock) -> IcloudAccount:
    """Return an account for a config entry added to hass."""
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


async def _set_up_with(
    hass: HomeAssistant, mock_store: Mock, device: dict[str, Any]
) -> IcloudAccount:
    """Set an account up against a single device."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = MockDevicesContainer(USER_INFO, [MockAppleDevice(device)])

        account = _build_account(hass, mock_store)
        with patch.object(account, "_schedule_next_fetch"):
            await hass.async_add_executor_job(account.setup)

    return account


@pytest.mark.parametrize(
    ("device", "is_tracked"),
    [
        pytest.param(DEVICE, True, id="battery_and_location"),
        pytest.param(DEVICE_WITHOUT_BATTERY, True, id="location_but_no_battery"),
        pytest.param(DEVICE_WITHOUT_LOCATION, False, id="battery_but_no_location"),
    ],
)
async def test_a_device_is_tracked_when_it_can_be_located(
    hass: HomeAssistant,
    mock_store: Mock,
    device: dict[str, Any],
    is_tracked: bool,
) -> None:
    """Test that being locatable decides tracking, not having a battery.

    iCloud reports no battery for a device that is asleep or has none of its
    own, and no location at all for an account that is not sharing one. Only
    the second has nothing to track.
    """
    account = await _set_up_with(hass, mock_store, device)

    assert (device["id"] in account.devices) is is_tracked


async def test_a_device_without_battery_still_reports_its_location(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test that a device iCloud reports no battery for gets its coordinates.

    Reading the location used to sit inside the battery block, so letting such
    a device through on its own would have tracked it with no coordinates.
    """
    account = await _set_up_with(hass, mock_store, DEVICE_WITHOUT_BATTERY)

    device = account.devices[DEVICE_WITHOUT_BATTERY["id"]]
    assert device.location == LOCATION
    assert device.battery_level is None
