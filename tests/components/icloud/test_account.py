"""Tests for the iCloud account."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAcceptTermsException,
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
)
from pyicloud.services.findmyiphone import AppleDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests import Response

from homeassistant.components.icloud.account import IcloudAccount
from homeassistant.components.icloud.const import (
    ATTR_BATTERY,
    ATTR_LOW_POWER_MODE,
    ATTR_OWNER_NAME,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_MAX_INTERVAL,
    DEVICE_STATUS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from . import MockAppleDevice, MockDevicesContainer
from .const import (
    DEVICE,
    DEVICE_WITH_HALF_A_LOCATION,
    DEVICE_WITHOUT_BATTERY,
    DEVICE_WITHOUT_LOCATION,
    DEVICE_WITHOUT_LOCATION_OR_BATTERY,
    LOCATION,
    MEMBER_1_FULL_NAME,
    MEMBER_1_PERSON_ID,
    MOCK_CONFIG,
    USER_INFO,
    USERNAME,
)


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
        # As the integration does. _determine_interval reaches the state
        # machine through run_callback_threadsafe, which refuses to run on
        # the event loop.
        await hass.async_add_executor_job(account.setup)

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
        await hass.async_add_executor_job(account.update_devices)
    assert mock_icloud_service.return_value.devices.refresh_calls == [True]


class LiveDevicesContainer:
    """Devices container that reports whatever payloads the test holds.

    Payloads can be changed, added and removed between polls, the way the
    devices of an iCloud account change from one poll to the next.
    """

    def __init__(self, user_info: dict[str, Any], payloads: list[dict]) -> None:
        """Keep the payloads the container reports."""
        self.user_info = user_info
        self._payloads = payloads

    def refresh(self, locate: bool = False) -> None:
        """Match the FindMyiPhone service interface."""

    def __iter__(self):
        """Iterate the devices as pyicloud reports them."""
        return iter([FakeAppleDevice(payload) for payload in self._payloads])

    def __len__(self) -> int:
        """Return the number of devices."""
        return len(self._payloads)

    def __getitem__(self, idx):
        """Return a device by position."""
        return FakeAppleDevice(self._payloads[idx])


@pytest.fixture(name="icloud_devices")
def mock_icloud_devices_fixture() -> Generator[list[dict[str, Any]]]:
    """Mock the iCloud service over device payloads a test can change."""
    payloads: list[dict[str, Any]] = []
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = LiveDevicesContainer(USER_INFO, payloads)
        yield payloads


async def _set_up_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration for a config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the account poll iCloud once more."""
    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _entities_of_device(hass: HomeAssistant, config_entry: MockConfigEntry) -> set[str]:
    """Return what the integration offers for the account's devices.

    The tracker platform and the battery sensors each build only what the
    device reports, so this names which of the two exist.
    """
    kinds = set()
    for entry in er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    ):
        if entry.domain == "device_tracker":
            kinds.add("tracker")
        elif entry.unique_id.endswith("_battery"):
            kinds.add("battery")
    return kinds


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        pytest.param(DEVICE, {"tracker", "battery"}, id="battery_and_location"),
        pytest.param(DEVICE_WITHOUT_BATTERY, {"tracker"}, id="location_but_no_battery"),
        pytest.param(
            DEVICE_WITHOUT_LOCATION, {"battery"}, id="battery_but_no_location"
        ),
        pytest.param(DEVICE_WITHOUT_LOCATION_OR_BATTERY, set(), id="neither"),
        pytest.param(DEVICE_WITH_HALF_A_LOCATION, set(), id="half_a_location_only"),
    ],
)
async def test_a_device_gets_what_it_reports(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    device: dict[str, Any],
    expected: set[str],
) -> None:
    """Test that a device is offered for each signal it reports, and only those.

    The account feeds both the tracker platform and the battery sensors, and
    each skips what it cannot use, so a device with only one of the two is
    still worth having. Filtering on the battery alone dropped a located
    device that reports none; filtering on the location alone would take the
    battery sensor away from a device that is not sharing one.
    """
    icloud_devices.append(device)

    config_entry = await _set_up_entry(hass)

    assert _entities_of_device(hass, config_entry) == expected


async def test_a_device_without_battery_still_reports_its_location(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
) -> None:
    """Test that a device iCloud reports no battery for gets its coordinates.

    Reading the location used to sit inside the battery block, so letting such
    a device through on its own would have tracked it with no coordinates.
    """
    icloud_devices.append(DEVICE_WITHOUT_BATTERY)

    await _set_up_entry(hass)

    state = hass.states.get("device_tracker.mac_mini")
    assert state.attributes[ATTR_LATITUDE] == LOCATION["latitude"]
    assert state.attributes[ATTR_LONGITUDE] == LOCATION["longitude"]
    assert ATTR_BATTERY not in state.attributes
    assert hass.states.get("sensor.mac_mini_battery") is None


@pytest.mark.parametrize(
    "location",
    [
        pytest.param({"latitude": 60.2, "longitude": None}, id="one-coordinate"),
        pytest.param({"latitude": 60.2, "longitude": 24.9}, id="no-accuracy"),
    ],
)
async def test_half_a_location_is_not_tracked(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    location: dict[str, Any],
) -> None:
    """Test that a fix missing anything the tracker reads is never used.

    The tracker and the polling interval read both coordinates and the
    accuracy, so keeping part of a fix would fail there rather than here. The
    device is still kept for its battery.
    """
    icloud_devices.append(DEVICE | {"location": location})

    await _set_up_entry(hass)

    assert hass.states.get("device_tracker.iphone") is None
    assert hass.states.get("sensor.iphone_battery").state == "80"


async def test_a_device_gaining_a_battery_gets_its_battery_sensor(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a battery arriving later still creates the battery sensor.

    A device kept for its location alone is added without one, and the sensor
    platform only builds from the new-device signal, so the battery it starts
    reporting would otherwise go unnoticed until Home Assistant restarts.
    """
    icloud_devices.append(DEVICE_WITHOUT_BATTERY)
    await _set_up_entry(hass)
    assert hass.states.get("sensor.mac_mini_battery") is None

    icloud_devices[0] = DEVICE_WITHOUT_BATTERY | {
        "batteryStatus": "NotCharging",
        "batteryLevel": 0.4,
    }
    await _poll(hass, freezer)

    assert hass.states.get("sensor.mac_mini_battery").state == "40"


async def test_devices_appearing_in_one_poll_all_get_their_entities(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the entities of every device that turns up in a poll are built.

    One poll can give a known device a battery and bring another device with
    it. The platforms are told once the poll has finished adding devices, as
    they iterate the account's devices while the poll adds them, and what they
    build then has to cover both.
    """
    icloud_devices.append(DEVICE_WITHOUT_BATTERY)
    await _set_up_entry(hass)

    icloud_devices[0] = DEVICE_WITHOUT_BATTERY | {
        "batteryStatus": "NotCharging",
        "batteryLevel": 0.4,
    }
    icloud_devices.append(DEVICE | {"id": "device9", "name": "iPad 9"})
    await _poll(hass, freezer)

    assert hass.states.get("sensor.mac_mini_battery").state == "40"
    assert hass.states.get("sensor.ipad_9_battery").state == "80"
    assert hass.states.get("device_tracker.ipad_9") is not None


async def test_a_battery_level_that_is_absent_is_not_zero(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a battery iCloud gives no level for is not shown as empty."""
    icloud_devices.append(DEVICE)
    await _set_up_entry(hass)
    assert hass.states.get("sensor.iphone_battery").state == "80"

    icloud_devices[0] = {
        key: value for key, value in DEVICE.items() if key != "batteryLevel"
    }
    await _poll(hass, freezer)

    assert hass.states.get("sensor.iphone_battery").state == STATE_UNKNOWN


async def test_a_device_losing_its_battery_stops_reporting_a_level(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a battery iCloud stops reporting is not remembered.

    Keeping a device whose battery disappears - one that has gone to sleep,
    say - would otherwise leave the level and the low-power flag at whatever
    they last were, which is what the sensor reads.
    """
    icloud_devices.append(DEVICE)
    await _set_up_entry(hass)
    assert hass.states.get("sensor.iphone_battery").state == "80"
    assert hass.states.get("device_tracker.iphone").attributes[ATTR_BATTERY] == 80

    icloud_devices[0] = DEVICE | {"batteryStatus": "Unknown", "batteryLevel": None}
    await _poll(hass, freezer)

    assert hass.states.get("sensor.iphone_battery").state == STATE_UNKNOWN
    attributes = hass.states.get("device_tracker.iphone").attributes
    assert ATTR_BATTERY not in attributes
    assert ATTR_LOW_POWER_MODE not in attributes


@pytest.mark.parametrize(
    "location",
    [
        pytest.param(None, id="no-location"),
        pytest.param({"latitude": 60.2, "longitude": None}, id="half-a-location"),
        pytest.param({"latitude": 60.2}, id="missing-longitude"),
        pytest.param({"latitude": 60.2, "longitude": 24.9}, id="missing-accuracy"),
        pytest.param({}, id="empty-location"),
    ],
)
async def test_a_device_that_stops_sharing_its_location_reads_unknown(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
    location: dict[str, Any] | None,
) -> None:
    """Test that a location iCloud stops reporting is not kept.

    The tracker would otherwise keep showing the last fix for as long as the
    device lasts.
    """
    icloud_devices.append(DEVICE_WITHOUT_BATTERY)
    await _set_up_entry(hass)
    state = hass.states.get("device_tracker.mac_mini")
    assert state.state != STATE_UNKNOWN
    assert state.attributes[ATTR_LATITUDE] == LOCATION["latitude"]

    icloud_devices[0] = DEVICE_WITHOUT_BATTERY | {"location": location}
    await _poll(hass, freezer)

    state = hass.states.get("device_tracker.mac_mini")
    assert state.state == STATE_UNKNOWN
    assert ATTR_LATITUDE not in state.attributes


async def test_a_tracked_device_is_updated_even_when_it_reports_nothing(
    hass: HomeAssistant,
    icloud_devices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device already tracked is kept current whatever it reports.

    What decides whether to start tracking a device must not decide whether to
    keep it up to date. Skipping the update would leave the battery and
    location it has stopped reporting on show for as long as the device lasts,
    which is the stale state clearing them was meant to prevent.
    """
    icloud_devices.append(DEVICE)
    await _set_up_entry(hass)
    assert hass.states.get("sensor.iphone_battery").state == "80"
    assert hass.states.get("device_tracker.iphone").state != STATE_UNKNOWN

    # The same device now reports neither signal.
    icloud_devices[0] = DEVICE | {
        "batteryStatus": "Unknown",
        "batteryLevel": None,
        "location": None,
    }
    await _poll(hass, freezer)

    assert hass.states.get("sensor.iphone_battery").state == STATE_UNKNOWN
    state = hass.states.get("device_tracker.iphone")
    assert state.state == STATE_UNKNOWN
    assert ATTR_BATTERY not in state.attributes


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


async def test_a_rejected_session_on_locate_reaches_the_caller(
    hass: HomeAssistant,
    mock_store: Mock,
    mock_icloud_service: MagicMock,
) -> None:
    """Test that a locate refused for authentication is not treated as best effort.

    Only a failure to locate is swallowed. A rejected session is what the
    caller acts on, by logging in again or asking the user, so it has to be
    raised instead of leaving every later poll to fail the same way.
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

        service.devices.refresh = Mock(
            side_effect=PyiCloudFailedLoginException("rejected")
        )
        with pytest.raises(PyiCloudFailedLoginException):
            await hass.async_add_executor_job(account.update_devices)


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


class FakeAppleDevice(AppleDevice):
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
        super().__init__(
            content,
            params={},
            manager=Mock(is_alive=True),
            sound_url="",
            lost_url="",
            erase_url="",
            erase_token_url="",
            message_url="",
        )

    def __getitem__(self, key):
        """Proxy into the raw payload, as AppleDevice does."""
        return self._content[key]


class MockDevicesWithLocation(MockDevicesContainer):
    """Devices container whose single device reports a location."""

    def refresh(self, locate: bool = True) -> None:
        """Match the FindMyiPhone service interface."""


class StrictAppleDevice(MockAppleDevice):
    """Mock device that reports its payload the way the real one does.

    AppleDevice.status() answers every requested field, using None for the
    ones iCloud left out, while __getitem__ reads self._content[key] directly
    and raises for them.
    """

    def status(self, key):
        """Return the requested fields, filling in the missing ones."""
        return {field: self._status.get(field) for field in key} | {
            field: value for field, value in self._status.items() if field not in key
        }

    def __getitem__(self, key):
        """Index the raw payload without normalising a missing key."""
        return self._status[key]


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


async def test_terms_acceptance_starts_reauth(hass: HomeAssistant) -> None:
    """Test that a login waiting on new terms asks the user to act.

    Only the config flow can accept them, so the account has to stay loaded
    with its fetch timer running while the reauth flow it started is open.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService",
        side_effect=PyiCloudAcceptTermsException("Terms not accepted"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        assert config_entry.runtime_data.api is None
        assert [
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["context"]["source"] == "reauth"
        ]


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


async def test_pending_check_ignores_a_skipped_device(hass: HomeAssistant) -> None:
    """Test that the pending-device retry does not read a device that was skipped.

    The first device iCloud lists has no id and is still loading, so it is
    skipped. Reading its status for the pending check would schedule a retry
    for a device that was never stored, when the one that was is online.
    """
    skipped = {**_located_device_status(0.8), "id": None, "deviceStatus": "203"}
    online = _located_device_status(0.8)

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        service_instance.devices = MockDevicesWithLocation(
            USER_INFO, [StrictAppleDevice(skipped), StrictAppleDevice(online)]
        )
        service_mock.return_value = service_instance

        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    account = config_entry.runtime_data
    assert list(account.devices) == ["device1"]
    # A pending first device would have shortened the interval to 15 seconds.
    assert account.fetch_interval != 0.25


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


async def test_2fa_exception_while_polling_asks_for_a_code(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a 2FA challenge raised while polling asks the user to log in.

    authenticate() raises out of the MFA options request before requires_2fa is
    set, so the exception is the only signal that a code is what is missing.
    Without it the challenge fell through to the transient handling and was
    retried every couple of minutes without ever asking the user.

    The session cannot carry the code while requires_2fa is unset, because that
    property is what async_step_reauth reads to open code entry. Keeping it
    would walk the flow past code entry and finish reauthentication with the
    challenge still outstanding, so it is dropped and the password is asked
    for: the login that follows re-issues the challenge with requires_2fa set.
    """
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    service.requires_2fa = False
    # Pinned: an unset MagicMock is truthy, which parks the flow on the
    # trusted-device form and hides where it really goes.
    service.requires_2sa = False
    service.authenticate.side_effect = PyiCloud2FARequiredException(
        USERNAME, Mock(spec=Response)
    )

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    # The flow waits on the user rather than completing without the code.
    assert [flow["step_id"] for flow in flows] == ["reauth_confirm"]
    assert config_entry.runtime_data.api is None


@pytest.mark.parametrize(
    "status",
    [
        AppleAuthError.TWO_FACTOR_REQUIRED,
        AppleAuthError.LOGIN_TOKEN_EXPIRED,
        AppleAuthError.FIND_MY_REAUTH_REQUIRED,
    ],
)
async def test_auth_status_while_polling_asks_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
    status: AppleAuthError,
) -> None:
    """Test that an authentication status while polling starts reauth.

    pyicloud only raises a dedicated exception for a 409 carrying an hsa2 body,
    so every other rejection arrives as a plain PyiCloudAPIResponseException and
    the status has to be inspected rather than the exception type.
    """
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    service.authenticate.side_effect = PyiCloudAPIResponseException(
        "Authentication required for Account.", status
    )

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_other_api_error_while_polling_keeps_retrying(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a non-authentication API error keeps the loop retrying.

    Reauthenticating cannot fix a server-side failure, so it has to be treated
    as transient and the next fetch still scheduled.
    """
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    service.authenticate.side_effect = PyiCloudAPIResponseException(
        "Service temporarily unavailable", 503
    )

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    # The session is kept and the loop keeps going rather than parking.
    assert config_entry.runtime_data.api is not None

    service.authenticate.side_effect = None
    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert service.authenticate.call_count > 1


async def test_family_device_after_setup_time_2fa(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an account challenged during setup still builds its devices.

    setup() returns before reading the account's owner and family names when
    iCloud asks for a verification code, and keep_alive() only runs a full
    setup again when there is no session at all. The names therefore have to
    be filled in by the poll that follows the challenge, or a family device
    can never be built.
    """
    service, status = polling_service
    status["prsId"] = MEMBER_1_PERSON_ID
    service.requires_2fa = True

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery") is None

    # The user enters the code.
    service.requires_2fa = False

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.iphone_battery")
    assert state is not None
    assert state.state == "80"
    assert state.attributes[ATTR_OWNER_NAME] == MEMBER_1_FULL_NAME


async def test_account_with_no_devices_keeps_polling(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an empty device response does not kill the account.

    iCloud answers with no devices while an account is still settling, and
    the status of the first device was read without checking there was one.
    """
    service, status = polling_service
    service.devices = MockDevicesWithLocation(USER_INFO, [])

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.iphone_battery") is None

    # The devices show up on a later poll.
    service.devices = MockDevicesWithLocation(USER_INFO, [FakeAppleDevice(status)])

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.iphone_battery").state == "80"


async def test_rejected_session_on_device_refresh_asks_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a session rejected while reading the devices reaches the user.

    Refreshing the devices is where a stored session is usually turned down,
    and that request was handled as an unknown error: retried every couple of
    minutes with nothing ever shown to the user.
    """
    service, _ = polling_service

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    type(service).devices = PropertyMock(
        side_effect=PyiCloudFailedLoginException("rejected")
    )

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_auth_status_on_first_device_refresh_asks_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an authentication status on the first fetch reaches the user.

    iCloud reports most rejections as an API response carrying the status
    rather than as a dedicated exception, and the first device refresh runs
    inside setup(), where an unhandled one would leave a dead entry.
    """
    service, _ = polling_service
    type(service).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException(
            "Authentication required for Account.", AppleAuthError.LOGIN_TOKEN_EXPIRED
        )
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Only the user can clear a rejection, so setup fails as an authentication
    # failure and Home Assistant starts the reauth flow and stops retrying.
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_rejected_session_on_first_device_refresh_asks_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
) -> None:
    """Test that a session rejected on the first fetch reaches the user.

    The exceptions pyicloud raises for a rejection, as opposed to a status on a
    plain response, end up in setup() as well, where an unhandled one would
    leave a dead entry.
    """
    service, _ = polling_service
    type(service).devices = PropertyMock(
        side_effect=PyiCloudFailedLoginException("rejected")
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_other_api_error_on_first_device_refresh_is_not_a_rejection(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
) -> None:
    """Test that an error that is not about authentication does not ask for a login.

    Only a status that says the session has to be established again is a reason
    to send the user to the password; anything else is iCloud failing, and the
    user cannot fix that by logging in.
    """
    service, _ = polling_service
    type(service).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException("Service unavailable", 503)
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is not ConfigEntryState.LOADED
    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_unreachable_icloud_on_first_device_refresh_retries_the_setup(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
) -> None:
    """Test that an unreachable iCloud is reported as a connection problem."""
    service, _ = polling_service
    type(service).devices = PropertyMock(
        side_effect=PyiCloudConnectionException(reason="Connection error")
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        config_entry.reason
        == "An error occurred while connecting to iCloud: Connection error"
    )
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    ("error", "reauth"),
    [
        pytest.param(
            PyiCloudAPIResponseException(
                "Authentication required", AppleAuthError.LOGIN_TOKEN_EXPIRED
            ),
            True,
            id="auth-status",
        ),
        pytest.param(PyiCloudFailedLoginException("rejected"), True, id="failed-login"),
        pytest.param(
            PyiCloudAPIResponseException("Service unavailable", 503),
            False,
            id="other-status",
        ),
    ],
)
async def test_devices_rejected_after_the_first_read_are_left_to_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    error: Exception,
    reauth: bool,
) -> None:
    """Test that a rejection from the closing device update reaches the user.

    The devices were read once to get this far, so this one rarely fails; when
    it does, the entry still loads and the timer keeps polling.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    with patch.object(IcloudAccount, "update_devices", side_effect=error):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert bool(hass.config_entries.flow.async_progress()) is reauth
    assert (config_entry.state is ConfigEntryState.LOADED) is reauth


async def test_auth_status_on_device_refresh_while_polling_asks_the_user(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a status from reading the devices while polling starts reauth.

    A rejected session is usually turned down when the devices are read rather
    than when logging in, and as a plain response carrying the status, so it
    is the status that has to be inspected to tell it from an outage.
    """
    service, _ = polling_service
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    type(service).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException(
            "Authentication required for Account.", AppleAuthError.LOGIN_TOKEN_EXPIRED
        )
    )

    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert config_entry.runtime_data.api is None


async def test_a_failed_setup_retry_keeps_the_account_polling(
    hass: HomeAssistant,
    polling_service: tuple[MagicMock, dict],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a poll that cannot rebuild the session still arms the next one.

    With no session and nobody being asked to log in, a poll builds the service
    again. Whatever that raises must not escape into the event loop, which
    would stop the account polling for good; it is logged and retried.

    keep_alive() is called directly with no reauth flow reported pending: the
    calendar and Reminders coordinators start one of their own for an account
    with no session, at a point that depends on timing, and a poll leaves the
    login to the user once one is outstanding.
    """
    del polling_service  # only the patched service class is needed here

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    account = config_entry.runtime_data
    account.api = None

    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService",
            side_effect=Exception("boom"),
        ),
        patch.object(account, "_schedule_next_fetch") as schedule,
        patch.object(account, "_reauth_pending", return_value=False),
    ):
        await hass.async_add_executor_job(account.keep_alive)

    assert "Error setting up iCloud account, will retry" in caplog.text
    assert account.api is None
    schedule.assert_called_once()

    # The next poll builds the session once iCloud lets it.
    with (
        patch.object(account, "_schedule_next_fetch"),
        patch.object(account, "_reauth_pending", return_value=False),
    ):
        await hass.async_add_executor_job(account.keep_alive)

    assert account.api is not None


async def test_device_without_a_status_keeps_the_account_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device iCloud reports no status for does not end setup.

    The pending-device check read the field straight off the payload, which
    raises for a device that does not carry it. update_devices() runs inside
    setup() before any timer is armed, so that left the entry loaded and never
    polling again.
    """
    status = _located_device_status(0.8)
    del status[DEVICE_STATUS]

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_instance = MagicMock()
        service_instance.requires_2fa = False
        service_instance.devices = MockDevicesWithLocation(
            USER_INFO, [StrictAppleDevice(status)]
        )
        service_mock.return_value = service_instance

        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        # The fetch timer is armed at the end of update_devices(), so reaching
        # a second fetch is what says the first one ran to the end.
        service_instance.authenticate.reset_mock()
        freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert service_instance.authenticate.called
