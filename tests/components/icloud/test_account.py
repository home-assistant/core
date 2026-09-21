"""Tests for the iCloud account."""

from unittest.mock import MagicMock, Mock, patch

from pyicloud.exceptions import PyiCloudException
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

from . import MockAppleDevice, MockDevicesContainer
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
        account.setup()

    assert account.api is not None
    assert account.owner_fullname == "user name"
    assert "johntravolta" in account.family_members_fullname
    assert account.family_members_fullname["johntravolta"] == "John TRAVOLTA"


def _account(hass: HomeAssistant, mock_store: Mock) -> IcloudAccount:
    """Return an account wired to the mocked service."""
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


async def test_poll_asks_icloud_to_locate_the_devices(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that a poll requests a fresh fix before the devices are read.

    Nothing else asks for one: reading `devices` only builds the service
    manager, and the background refresh pyicloud runs alongside it leaves
    `locate` at its default of False. Without this request the integration
    only ever sees whichever fix iCloud is already holding, which is the
    very thing the staleness check then discards.
    """
    account = _account(hass, mock_store)

    with patch.object(account, "_schedule_next_fetch"):
        account.setup()
        account.keep_alive()

    assert mock_icloud_service.devices.locate_requests == [True]


async def test_devices_are_read_even_when_the_locate_request_fails(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that a failed locate does not stop the poll.

    Locating is best effort. The cached fixes are still worth reading, so a
    failure here must not cost the account its update.
    """
    account = _account(hass, mock_store)

    with patch.object(account, "_schedule_next_fetch"):
        account.setup()
        mock_icloud_service.devices.refresh = Mock(
            side_effect=PyiCloudException("locate unavailable")
        )
        account.keep_alive()

    assert account.devices


async def test_no_locate_requested_while_a_verification_code_is_pending(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that no locate is requested while the account needs 2FA.

    The session cannot serve one, and asking would only add a failed call to
    an account that is already waiting on the user.
    """
    account = _account(hass, mock_store)

    with patch.object(account, "_schedule_next_fetch"):
        account.setup()
        mock_icloud_service.devices.locate_requests.clear()
        mock_icloud_service.requires_2fa = True
        with patch.object(account, "_require_reauth"):
            account.keep_alive()

    assert mock_icloud_service.devices.locate_requests == []
