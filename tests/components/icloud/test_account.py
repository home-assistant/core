"""Tests for the iCloud account."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
)
from pyicloud.services.findmyiphone import AppleDevice
import pytest
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
from homeassistant.components.icloud.device_tracker import IcloudTrackerEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_LATITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.storage import Store

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
    ("device", "is_kept"),
    [
        pytest.param(DEVICE, True, id="battery_and_location"),
        pytest.param(DEVICE_WITHOUT_BATTERY, True, id="location_but_no_battery"),
        pytest.param(DEVICE_WITHOUT_LOCATION, True, id="battery_but_no_location"),
        pytest.param(DEVICE_WITHOUT_LOCATION_OR_BATTERY, False, id="neither"),
        pytest.param(DEVICE_WITH_HALF_A_LOCATION, False, id="half_a_location_only"),
    ],
)
async def test_a_device_is_kept_when_either_signal_is_usable(
    hass: HomeAssistant,
    mock_store: Mock,
    device: dict[str, Any],
    is_kept: bool,
) -> None:
    """Test that a device is dropped only when it reports neither signal.

    The account feeds both the tracker platform and the battery sensors, and
    each skips what it cannot use, so a device with only one of the two is
    still worth keeping. Filtering on the battery alone dropped a located
    device that reports none; filtering on the location alone would take the
    battery sensor away from a device that is not sharing one.
    """
    account = await _set_up_with(hass, mock_store, device)

    assert (device["id"] in account.devices) is is_kept


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


@pytest.mark.parametrize(
    "location",
    [
        pytest.param({"latitude": 60.2, "longitude": None}, id="one-coordinate"),
        pytest.param({"latitude": 60.2, "longitude": 24.9}, id="no-accuracy"),
    ],
)
async def test_half_a_location_is_not_stored(
    hass: HomeAssistant,
    mock_store: Mock,
    location: dict[str, Any],
) -> None:
    """Test that a fix missing anything the tracker reads is never stored.

    The tracker and the polling interval read both coordinates and the
    accuracy, so keeping part of a fix would fail there rather than here. The
    device is still kept for its battery.
    """
    account = await _set_up_with(hass, mock_store, DEVICE | {"location": location})

    device = account.devices[DEVICE["id"]]
    assert device.location is None
    assert device.battery_level == 80


async def test_a_device_gaining_a_battery_gets_its_battery_sensor(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test that a battery arriving later still creates the battery sensor.

    A device kept for its location alone is added without one, and the sensor
    platform only builds from the new-device signal, so the battery it starts
    reporting would otherwise go unnoticed until Home Assistant restarts.
    """

    def battery_sensors() -> list[str]:
        return [
            entity_id
            for entity_id in hass.states.async_entity_ids("sensor")
            if entity_id.endswith("_battery")
        ]

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = MockDevicesContainer(
            USER_INFO, [MockAppleDevice(DEVICE_WITHOUT_BATTERY)]
        )

        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert battery_sensors() == []

        account = config_entry.runtime_data
        device = account.devices[DEVICE_WITHOUT_BATTERY["id"]]
        await hass.async_add_executor_job(
            device.update,
            DEVICE_WITHOUT_BATTERY
            | {"batteryStatus": "NotCharging", "batteryLevel": 0.4},
        )
        await hass.async_block_till_done()

    assert device.battery_level == 40
    assert battery_sensors() != []


async def test_a_battery_level_that_is_absent_is_not_zero(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test that a battery iCloud gives no level for is not shown as empty."""
    account = await _set_up_with(hass, mock_store, DEVICE)
    device = account.devices[DEVICE["id"]]
    assert device.battery_level == 80

    status = {key: value for key, value in DEVICE.items() if key != "batteryLevel"}
    await hass.async_add_executor_job(device.update, status)

    assert device.battery_level is None


async def test_a_device_losing_its_battery_stops_reporting_a_level(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test that a battery iCloud stops reporting is not remembered.

    Keeping a device whose battery disappears - one that has gone to sleep,
    say - would otherwise leave the level and the low-power flag at whatever
    they last were, which is what the sensor reads.
    """
    account = await _set_up_with(hass, mock_store, DEVICE)
    device = account.devices[DEVICE["id"]]
    assert device.battery_level == 80

    # Off the loop, as the account does: update() announces through the
    # thread-safe dispatcher_send.
    await hass.async_add_executor_job(
        device.update, DEVICE | {"batteryStatus": "Unknown", "batteryLevel": None}
    )

    assert device.battery_level is None
    assert ATTR_BATTERY not in device.extra_state_attributes
    assert ATTR_LOW_POWER_MODE not in device.extra_state_attributes


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
    mock_store: Mock,
    location: dict[str, Any] | None,
) -> None:
    """Test that a location iCloud stops reporting is not kept.

    The tracker would otherwise keep showing the last fix for as long as the
    device lasts.
    """
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = MockDevicesContainer(
            USER_INFO, [MockAppleDevice(DEVICE_WITHOUT_BATTERY)]
        )

        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        account = config_entry.runtime_data
        [tracker] = hass.states.async_entity_ids("device_tracker")
        assert hass.states.get(tracker).state != STATE_UNKNOWN
        assert (
            hass.states.get(tracker).attributes[ATTR_LATITUDE] == LOCATION["latitude"]
        )

        device = account.devices[DEVICE_WITHOUT_BATTERY["id"]]
        await hass.async_add_executor_job(
            device.update, DEVICE_WITHOUT_BATTERY | {"location": location}
        )
        dispatcher_send(hass, account.signal_device_update)
        await hass.async_block_till_done()

    assert device.location is None
    state = hass.states.get(tracker)
    assert state.state == STATE_UNKNOWN
    assert ATTR_LATITUDE not in state.attributes


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        pytest.param("latitude", 1.0, id="latitude"),
        pytest.param("longitude", 2.0, id="longitude"),
        pytest.param("location_accuracy", 10, id="accuracy"),
    ],
)
def test_tracker_reads_the_location_once(attribute: str, expected: float) -> None:
    """Test that a location cleared mid-read cannot break the tracker.

    The poll clears the location from the executor, so it can be gone between
    checking it and reading a coordinate out of it.
    """
    device = MagicMock()
    type(device).location = PropertyMock(
        side_effect=[_located_device_status(0.8)["location"], None, None]
    )
    tracker = IcloudTrackerEntity(MagicMock(), device)

    assert getattr(tracker, attribute) == expected


async def test_a_tracked_device_is_updated_even_when_it_reports_nothing(
    hass: HomeAssistant,
    mock_store: Mock,
) -> None:
    """Test that a device already tracked is kept current whatever it reports.

    What decides whether to start tracking a device must not decide whether to
    keep it up to date. Skipping the update would leave the battery and
    location it has stopped reporting on show for as long as the device lasts,
    which is the stale state clearing them was meant to prevent.
    """
    status = dict(DEVICE)

    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service = service_mock.return_value
        service.requires_2fa = False
        service.devices = MockDevicesContainer(USER_INFO, [MockAppleDevice(status)])

        account = _build_account(hass, mock_store)
        with patch.object(account, "_schedule_next_fetch"):
            await hass.async_add_executor_job(account.setup)

            device = account.devices[DEVICE["id"]]
            assert device.battery_level == 80
            assert device.location is not None

            # The same device now reports neither signal.
            status.update(
                {"batteryStatus": "Unknown", "batteryLevel": None, "location": None}
            )
            await hass.async_add_executor_job(account.update_devices)

    assert device.battery_level is None
    assert device.location is None
    assert ATTR_BATTERY not in device.extra_state_attributes


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

    assert config_entry.state is ConfigEntryState.LOADED
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

    assert config_entry.state is ConfigEntryState.LOADED
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
