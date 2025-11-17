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

from .const import MOCK_CONFIG, USERNAME

from tests.common import MockConfigEntry


class IterableDict(dict):
    """A dict that can be iterated over custom items."""

    def __init__(self, *args, iter_items=None, **kwargs) -> None:
        """Initialize the dict with optional iterable items."""
        super().__init__(*args, **kwargs)
        self._iter_items = iter_items or []

    def __iter__(self):
        """Iterate over the custom items."""
        return iter(self._iter_items)


@pytest.fixture(name="mock_store")
def mock_store_fixture():
    """Mock the storage."""
    with patch("homeassistant.components.icloud.account.Store") as store_mock:
        store_instance = Mock(spec=Store)
        store_instance.path = "/mock/path"
        store_mock.return_value = store_instance
        yield store_instance


@pytest.fixture(name="mock_icloud_service")
def mock_icloud_service_fixture():
    """Mock PyiCloudService with devices as dict."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False

        # Mock device for iteration
        mock_device = MagicMock()
        mock_device.status.return_value = {
            "id": "device1",
            "name": "iPhone",
            "deviceStatus": "200",
            "batteryStatus": "NotCharging",
            "batteryLevel": 0.8,
            "rawDeviceModel": "iPhone14,2",
            "deviceClass": "iPhone",
            "deviceDisplayName": "iPhone",
            "prsId": None,
            "lowPowerMode": False,
            "location": None,
        }
        # Make device indexable like a dict (for account.py line 211)
        mock_device.__getitem__ = lambda self, key: {
            "deviceStatus": "200",
        }.get(key)

        # Mock devices as dict with userInfo, iterable over devices
        mock_devices = IterableDict(
            {
                "userInfo": {
                    "firstName": "John",
                    "lastName": "Doe",
                    "membersInfo": {
                        "person1": {
                            "firstName": "Jane",
                            "lastName": "Doe",
                        }
                    },
                }
            },
            iter_items=[mock_device],
        )

        service_instance.devices = mock_devices
        service_mock.return_value = service_instance
        yield service_instance


@pytest.fixture(name="mock_icloud_service_no_userinfo")
def mock_icloud_service_no_userinfo_fixture():
    """Mock PyiCloudService with devices as dict but no userInfo."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        service_instance.devices = {}
        service_mock.return_value = service_instance
        yield service_instance


@pytest.fixture(name="mock_icloud_service_not_dict")
def mock_icloud_service_not_dict_fixture():
    """Mock PyiCloudService with devices as object (not dict)."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        # Return a non-dict object
        service_instance.devices = Mock()
        service_mock.return_value = service_instance
        yield service_instance


async def test_setup_success_with_dict_devices(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test successful setup with devices as dict."""
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
    assert account.owner_fullname == "John Doe"
    assert "person1" in account.family_members_fullname
    assert account.family_members_fullname["person1"] == "Jane Doe"


async def test_setup_fails_when_userinfo_missing(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service_no_userinfo: MagicMock,
) -> None:
    """Test setup fails when userInfo is missing from devices dict."""
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


async def test_setup_fails_when_devices_not_dict(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service_not_dict: MagicMock,
) -> None:
    """Test setup fails when devices is not a dict."""
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

    with pytest.raises(ConfigEntryNotReady, match="not a dictionary"):
        account.setup()


async def test_setup_with_family_members_info(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test setup correctly extracts family members info."""
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

    assert account.family_members_fullname["person1"] == "Jane Doe"


async def test_setup_without_family_members_info(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test setup without family members info."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False

        # Mock device for iteration
        mock_device = MagicMock()
        mock_device.status.return_value = {
            "id": "device1",
            "name": "iPhone",
            "deviceStatus": "200",
            "batteryStatus": "NotCharging",
            "batteryLevel": 0.8,
            "rawDeviceModel": "iPhone14,2",
            "deviceClass": "iPhone",
            "deviceDisplayName": "iPhone",
            "prsId": None,
            "lowPowerMode": False,
            "location": None,
        }
        # Make device indexable like a dict (for account.py line 211)
        mock_device.__getitem__ = lambda self, key: {
            "deviceStatus": "200",
        }.get(key)

        # Mock devices as dict with userInfo, iterable over devices
        mock_devices = IterableDict(
            {
                "userInfo": {
                    "firstName": "John",
                    "lastName": "Doe",
                }
            },
            iter_items=[mock_device],
        )

        service_instance.devices = mock_devices
        service_mock.return_value = service_instance

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

        assert account.owner_fullname == "John Doe"
        assert account.family_members_fullname == {}
