"""Tests for the iCloud account."""

from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.exceptions import PyiCloudFailedLoginException
from pyicloud.services.findmyiphone import AppleDevice
import pytest

from homeassistant.components.icloud.account import IcloudAccount
from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_MAX_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from .const import DEVICE, MOCK_CONFIG, USER_INFO, USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed


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
        account.setup()

    assert account.api is not None
    assert account.owner_fullname == "user name"
    assert "johntravolta" in account.family_members_fullname
    assert account.family_members_fullname["johntravolta"] == "John TRAVOLTA"


class FakeAppleDevice:
    """A device that reports status through pyicloud's own implementation.

    Reusing AppleDevice.status keeps these tests honest about how iCloud data
    actually reaches the integration: it reports every requested field, using
    None for the ones the payload omits, so a stand-in that raised KeyError
    would be testing a case that cannot happen.
    """

    # Bound to pyicloud's implementation, which only reads _content.
    status = AppleDevice.status

    def __init__(self, content: dict) -> None:
        """Store the payload iCloud would have returned."""
        self._content = content

    def __getitem__(self, key):
        """Proxy into the raw payload, as AppleDevice does."""
        return self._content[key]


class MockDevicesWithLocation(MockDevicesContainer):
    """Devices container whose single device reports a location."""

    def refresh(self, locate: bool = True) -> None:
        """Match the FindMyiPhone service interface."""


def _located_device_status(battery_level: float) -> dict:
    """Return a device status carrying a usable location."""
    return {
        **DEVICE,
        "batteryLevel": battery_level,
        "location": {
            "latitude": 1.0,
            "longitude": 2.0,
            "horizontalAccuracy": 10,
        },
    }


@pytest.fixture(name="polling_service")
def mock_polling_service_fixture():
    """Mock a service whose device can change between fetches."""
    status = _located_device_status(0.8)
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        service_instance.devices = MockDevicesWithLocation(
            USER_INFO, [FakeAppleDevice(status)]
        )
        service_mock.return_value = service_instance
        yield service_instance, status


async def test_polling_survives_authentication_error(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failing fetch does not stop the account from polling."""
    service, status = polling_service

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "80"

    # A transient failure used to escape the timer callback, after which no
    # further fetch was ever scheduled.
    service.authenticate.side_effect = ConnectionError("boom")

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The account recovers and the next fetch still happens.
    service.authenticate.side_effect = None
    status["batteryLevel"] = 0.5

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "50"


async def test_failed_login_is_not_retried_under_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a rejected login is left for the user to fix.

    The account still has to keep its fetch timer, which is only armed once
    update_devices() completes, so it used to sit loaded with no timer at all.
    But retrying the login while the user is already being asked to log in
    either adds failed attempts against their account or quietly succeeds and
    strands the repair they were shown. Finishing that flow reloads the entry,
    which is what recovers the account.
    """
    del polling_service  # only the patched service class is needed here

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService",
        side_effect=PyiCloudFailedLoginException("nope"),
    ) as service:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.runtime_data.api is None
        assert [
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["context"]["source"] == "reauth"
        ]
        attempts = service.call_count

        freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # The timer fired, but it did not try to log in again.
        assert service.call_count == attempts

    assert hass.states.get("sensor.iphone_battery") is None


async def test_device_without_identity_is_skipped(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device with no id is skipped rather than stored.

    pyicloud reports every requested field, using None for the ones iCloud
    left out, so an unusable device arrives looking like any other rather
    than raising on access.
    """
    _, status = polling_service
    status["id"] = None

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Nothing is stored under a None identity, so no entity is built from one.
    assert config_entry.runtime_data.devices == {}
    assert hass.states.get("sensor.iphone_battery") is None

    # A later poll picks the device up once iCloud reports it properly.
    status["id"] = "device1"

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "80"


async def test_polling_resumes_after_2fa_challenge(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that polling continues across a 2FA challenge.

    update_devices() returns early while a code is outstanding, which used to
    leave nothing to schedule the fetch that would notice it had been entered.
    """
    service, status = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.iphone_battery").state == "80"

    # iCloud starts asking for a verification code.
    service.requires_2fa = True
    status["batteryLevel"] = 0.6

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "80"

    # The user enters the code; polling has to pick up again on its own.
    service.requires_2fa = False

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "60"


async def test_rejected_credentials_ask_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a rejected login starts reauth instead of retrying forever."""
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    service.authenticate.side_effect = PyiCloudFailedLoginException("rejected")

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The user is asked to log in again rather than the session being retried
    # every couple of minutes indefinitely.
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_2fa_challenge_keeps_session_for_reauth(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a 2FA challenge while polling keeps the session.

    async_step_reauth reuses this session to send and validate the code and
    sends a None api back to the password form instead, so a challenge must
    not clear it.
    """
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    service.requires_2fa = True
    service.authenticate.side_effect = PyiCloudFailedLoginException("2FA required")

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.api is not None
