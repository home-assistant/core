"""The tests for the UniFi Network device tracker platform."""

from datetime import timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from aiounifi.models.event import EventKey
from aiounifi.models.message import MessageKey
from freezegun.api import FrozenDateTimeFactory, freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_IGNORE_WIRED_BUG,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DEFAULT_DETECTION_TIME,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

WIRED_CLIENT_1 = {
    "hostname": "wd_client_1",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:02",
}

WIRELESS_CLIENT_1 = {
    "ap_mac": "00:00:00:00:02:01",
    "essid": "ssid",
    "hostname": "ws_client_1",
    "ip": "10.0.0.1",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
}

WIRED_BUG_CLIENT = {
    "essid": "ssid",
    "hostname": "wd_bug_client",
    "ip": "10.0.0.3",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:03",
}

UNSEEN_CLIENT = {
    "essid": "ssid",
    "hostname": "unseen_client",
    "ip": "10.0.0.4",
    "is_wired": True,
    "last_seen": None,
    "mac": "00:00:00:00:00:04",
}

SWITCH_1 = {
    "board_rev": 3,
    "device_id": "mock-id-1",
    "has_fan": True,
    "fan_level": 0,
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "Switch 1",
    "next_interval": 20,
    "overheating": True,
    "state": 1,
    "type": "usw",
    "upgradable": True,
    "version": "4.0.42.10433",
}


@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT_1, WIRELESS_CLIENT_1]])
@pytest.mark.parametrize("device_payload", [[SWITCH_1]])
@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}]],
)
@pytest.mark.usefixtures("mock_device_registry")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data with and without admin rights."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.DEVICE_TRACKER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "client_payload", [[WIRELESS_CLIENT_1, WIRED_BUG_CLIENT, UNSEEN_CLIENT]]
)
@pytest.mark.parametrize("known_wireless_clients", [[WIRED_BUG_CLIENT["mac"]]])
@pytest.mark.usefixtures("mock_device_registry")
async def test_client_state_update(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify tracking of wireless clients."""
    # A normal client with current timestamp should have STATE_HOME, this is wired bug
    client_payload[1] |= {"last_seen": dt_util.as_timestamp(dt_util.utcnow())}
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME
    assert (
        hass.states.get("device_tracker.ws_client_1").attributes["host_name"]
        == "ws_client_1"
    )

    # Wireless client with wired bug, if bug active on restart mark device away
    assert hass.states.get("device_tracker.wd_bug_client").state == STATE_NOT_HOME

    # A client that has never been seen should be marked away.
    assert hass.states.get("device_tracker.unseen_client").state == STATE_NOT_HOME

    # Updated timestamp marks client as home
    ws_client_1 = client_payload[0] | {
        "last_seen": dt_util.as_timestamp(dt_util.utcnow())
    }
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Change time to mark client as away
    new_time = dt_util.utcnow() + timedelta(seconds=DEFAULT_DETECTION_TIME)
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # Same timestamp doesn't explicitly mark client as away
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME


@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT_1]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("mock_device_registry")
async def test_client_state_from_event_source(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_websocket_message: WebsocketMessageMock,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify update state of client based on event source."""

    async def mock_event(client: dict[str, Any], event_key: EventKey) -> dict[str, Any]:
        """Create and send event based on client payload."""
        event = {
            "user": client["mac"],
            "ssid": client["essid"],
            "hostname": client["hostname"],
            "ap": client["ap_mac"],
            "duration": 467,
            "bytes": 459039,
            "key": event_key,
            "subsystem": "wlan",
            "site_id": "name",
            "time": 1587752927000,
            "datetime": "2020-04-24T18:28:47Z",
            "_id": "5ea32ff730c49e00f90dca1a",
        }
        mock_websocket_message(message=MessageKey.EVENT, data=event)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # State change signalling works with events

    # Connected event
    await mock_event(client_payload[0], EventKey.WIRELESS_CLIENT_CONNECTED)
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Disconnected event
    await mock_event(client_payload[0], EventKey.WIRELESS_CLIENT_DISCONNECTED)
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Change time to mark client as away
    freezer.tick(timedelta(seconds=(DEFAULT_DETECTION_TIME + 1)))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # To limit false positives in client tracker
    # data sources are prioritized when available
    # once real data is received events will be ignored.

    # New data
    ws_client_1 = client_payload[0] | {
        "last_seen": dt_util.as_timestamp(dt_util.utcnow())
    }
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Disconnection event will be ignored
    await mock_event(client_payload[0], EventKey.WIRELESS_CLIENT_DISCONNECTED)
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Change time to mark client as away
    freezer.tick(timedelta(seconds=(DEFAULT_DETECTION_TIME + 1)))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME


@pytest.mark.parametrize("device_payload", [[SWITCH_1]])
@pytest.mark.usefixtures("mock_device_registry")
@pytest.mark.parametrize(
    ("state", "interval", "expected"),
    [
        # Start home, new signal but still home, heartbeat timer triggers away
        (1, 20, (STATE_HOME, STATE_HOME, STATE_NOT_HOME)),
        # Start away, new signal but still home, heartbeat time do not trigger
        (0, 40, (STATE_NOT_HOME, STATE_HOME, STATE_HOME)),
    ],
)
async def test_tracked_device_state_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    state: int,
    interval: int,
    expected: list[str],
) -> None:
    """Test the update_items function with some devices."""
    device_payload[0] = device_payload[0] | {"state": state}
    await config_entry_factory()
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("device_tracker.switch_1").state == expected[0]

    # State change signalling work
    switch_1 = device_payload[0] | {"state": 1, "next_interval": interval}
    mock_websocket_message(message=MessageKey.DEVICE, data=[switch_1])
    await hass.async_block_till_done()

    # Too little time has passed
    assert hass.states.get("device_tracker.switch_1").state == expected[1]

    # Change of time can mark device not_home outside of expected reporting interval
    new_time = dt_util.utcnow() + timedelta(seconds=90)
    freezer.move_to(new_time)
    async_fire_time_changed(hass, new_time)
    await hass.async_block_till_done()

    # Heartbeat to update state is interval + 60 seconds
    assert hass.states.get("device_tracker.switch_1").state == expected[2]

    # Disabled device is unavailable
    switch_1["disabled"] = True
    mock_websocket_message(message=MessageKey.DEVICE, data=switch_1)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.switch_1").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT_1, WIRED_CLIENT_1]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("mock_device_registry")
async def test_remove_clients(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    client_payload: list[dict[str, Any]],
) -> None:
    """Test the remove_items function with some clients."""
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.ws_client_1")
    assert hass.states.get("device_tracker.wd_client_1")

    # Remove client
    mock_websocket_message(message=MessageKey.CLIENT_REMOVED, data=client_payload[0])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert not hass.states.get("device_tracker.ws_client_1")
    assert hass.states.get("device_tracker.wd_client_1")


@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT_1]])
@pytest.mark.parametrize("device_payload", [[SWITCH_1]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("mock_device_registry")
async def test_hub_state_change(
    hass: HomeAssistant,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Verify entities state reflect on hub connection becoming unavailable."""
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.switch_1").state == STATE_HOME

    # Controller unavailable
    await mock_websocket_state.disconnect()
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_UNAVAILABLE
    assert hass.states.get("device_tracker.switch_1").state == STATE_UNAVAILABLE

    # Controller available
    await mock_websocket_state.reconnect()
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.switch_1").state == STATE_HOME


@pytest.mark.usefixtures("mock_device_registry")
async def test_option_ssid_filter(
    hass: HomeAssistant,
    mock_websocket_message,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
) -> None:
    """Test the SSID filter works.

    Client will travel from a supported SSID to an unsupported ssid.
    Client on SSID2 will be removed on change of options.
    """
    client_payload += [
        WIRELESS_CLIENT_1 | {"last_seen": dt_util.as_timestamp(dt_util.utcnow())},
        {
            "essid": "ssid2",
            "hostname": "client_on_ssid2",
            "is_wired": False,
            "last_seen": 1562600145,
            "mac": "00:00:00:00:00:02",
        },
    ]
    config_entry = await config_entry_factory()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_NOT_HOME

    # Setting SSID filter will remove clients outside of filter
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_SSID_FILTER: ["ssid"]}
    )
    await hass.async_block_till_done()

    # Not affected by SSID filter
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Removed due to SSID filter
    assert not hass.states.get("device_tracker.client_on_ssid2")

    # Roams to SSID outside of filter
    ws_client_1 = client_payload[0] | {"essid": "other_ssid"}
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)

    # Data update while SSID filter is in effect shouldn't create the client
    client_on_ssid2 = client_payload[1] | {
        "last_seen": dt_util.as_timestamp(dt_util.utcnow())
    }
    mock_websocket_message(message=MessageKey.CLIENT, data=client_on_ssid2)
    await hass.async_block_till_done()

    new_time = dt_util.utcnow() + timedelta(seconds=(DEFAULT_DETECTION_TIME + 1))
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # SSID filter marks client as away
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # SSID still outside of filter
    assert not hass.states.get("device_tracker.client_on_ssid2")

    # Remove SSID filter
    hass.config_entries.async_update_entry(config_entry, options={CONF_SSID_FILTER: []})
    await hass.async_block_till_done()

    ws_client_1["last_seen"] += 1
    client_on_ssid2["last_seen"] += 1
    mock_websocket_message(
        message=MessageKey.CLIENT, data=[ws_client_1, client_on_ssid2]
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_HOME

    # Time pass to mark client as away
    new_time += timedelta(seconds=(DEFAULT_DETECTION_TIME + 1))
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    client_on_ssid2["last_seen"] += 1
    mock_websocket_message(message=MessageKey.CLIENT, data=client_on_ssid2)
    await hass.async_block_till_done()

    # Client won't go away until after next update
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_HOME

    # Trigger update to get client marked as away
    client_on_ssid2["last_seen"] += 1
    mock_websocket_message(message=MessageKey.CLIENT, data=client_on_ssid2)
    await hass.async_block_till_done()

    new_time += timedelta(seconds=DEFAULT_DETECTION_TIME)
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_NOT_HOME


@pytest.mark.usefixtures("mock_device_registry")
async def test_wireless_client_go_wired_issue(
    hass: HomeAssistant,
    mock_websocket_message,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
) -> None:
    """Test the solution to catch wireless device go wired UniFi issue.

    UniFi Network has a known issue that when a wireless device goes away it sometimes gets marked as wired.
    """
    client_payload.append(
        WIRELESS_CLIENT_1 | {"last_seen": dt_util.as_timestamp(dt_util.utcnow())}
    )
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Trigger wired bug
    ws_client_1 = client_payload[0] | {
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "is_wired": True,
    }
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Wired bug fix keeps client marked as wireless
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Pass time
    new_time = dt_util.utcnow() + timedelta(seconds=DEFAULT_DETECTION_TIME)
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Marked as home according to the timer
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # Try to mark client as connected
    ws_client_1["last_seen"] += 1
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Make sure it don't go online again until wired bug disappears
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # Make client wireless
    ws_client_1["last_seen"] += 1
    ws_client_1["is_wired"] = False
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Client is no longer affected by wired bug and can be marked online
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME


@pytest.mark.parametrize("config_entry_options", [{CONF_IGNORE_WIRED_BUG: True}])
@pytest.mark.usefixtures("mock_device_registry")
async def test_option_ignore_wired_bug(
    hass: HomeAssistant,
    mock_websocket_message,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
) -> None:
    """Test option to ignore wired bug."""
    client_payload.append(
        WIRELESS_CLIENT_1 | {"last_seen": dt_util.as_timestamp(dt_util.utcnow())}
    )
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Trigger wired bug
    ws_client_1 = client_payload[0]
    ws_client_1["is_wired"] = True
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Wired bug in effect
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Pass time
    new_time = dt_util.utcnow() + timedelta(seconds=DEFAULT_DETECTION_TIME)
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Timer marks client as away
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_NOT_HOME

    # Mark client as connected again
    ws_client_1["last_seen"] += 1
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Ignoring wired bug allows client to go home again even while affected
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME

    # Make client wireless
    ws_client_1["last_seen"] += 1
    ws_client_1["is_wired"] = False
    mock_websocket_message(message=MessageKey.CLIENT, data=ws_client_1)
    await hass.async_block_till_done()

    # Client is wireless and still connected
    assert hass.states.get("device_tracker.ws_client_1").state == STATE_HOME


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_BLOCK_CLIENT: ["00:00:00:00:00:03"]}]
)
@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT_1]])
@pytest.mark.parametrize(
    "clients_all_payload",
    [
        [
            {
                "hostname": "restored",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:03",
            },
            {  # Not previously seen by integration, will not be restored
                "hostname": "not_restored",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:04",
            },
        ]
    ],
)
@pytest.mark.usefixtures("mock_device_registry")
async def test_restoring_client(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
    clients_all_payload: list[dict[str, Any]],
) -> None:
    """Verify clients are restored from clients_all if they ever was registered to entity registry."""
    entity_registry.async_get_or_create(  # Make sure unique ID converts to site_id-mac
        TRACKER_DOMAIN,
        UNIFI_DOMAIN,
        f"{clients_all_payload[0]['mac']}-site_id",
        suggested_object_id=clients_all_payload[0]["hostname"],
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(  # Unique ID already follow format site_id-mac
        TRACKER_DOMAIN,
        UNIFI_DOMAIN,
        f"site_id-{client_payload[0]['mac']}",
        suggested_object_id=client_payload[0]["hostname"],
        config_entry=config_entry,
    )

    await config_entry_factory()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.wd_client_1")
    assert hass.states.get("device_tracker.restored")
    assert not hass.states.get("device_tracker.not_restored")


@pytest.mark.parametrize(
    ("config_entry_options", "counts", "expected"),
    [
        (
            {CONF_TRACK_CLIENTS: True},
            (3, 1),
            ((True, True, True), (None, None, True)),
        ),
        (
            {CONF_TRACK_CLIENTS: True, CONF_SSID_FILTER: ["ssid"]},
            (3, 1),
            ((True, True, True), (None, None, True)),
        ),
        (
            {CONF_TRACK_CLIENTS: True, CONF_SSID_FILTER: ["ssid-2"]},
            (2, 1),
            ((None, True, True), (None, None, True)),
        ),
        (
            {CONF_TRACK_CLIENTS: False, CONF_CLIENT_SOURCE: ["00:00:00:00:00:01"]},
            (2, 1),
            ((True, None, True), (None, None, True)),
        ),
        (
            {CONF_TRACK_CLIENTS: False, CONF_CLIENT_SOURCE: ["00:00:00:00:00:02"]},
            (2, 1),
            ((None, True, True), (None, None, True)),
        ),
        (
            {CONF_TRACK_WIRED_CLIENTS: True},
            (3, 2),
            ((True, True, True), (True, None, True)),
        ),
        (
            {CONF_TRACK_DEVICES: True},
            (3, 2),
            ((True, True, True), (True, True, None)),
        ),
    ],
)
@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT_1, WIRED_CLIENT_1]])
@pytest.mark.parametrize("device_payload", [[SWITCH_1]])
@pytest.mark.usefixtures("mock_device_registry")
async def test_config_entry_options_track(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    config_entry_options: MappingProxyType[str, Any],
    counts: tuple[int],
    expected: tuple[tuple[bool | None, ...], ...],
) -> None:
    """Test the different config entry options.

    Validates how many entities are created
    and that the specific ones exist as expected.
    """
    option = next(iter(config_entry_options))

    def assert_state(state: State | None, expected: bool | None):
        """Assert if state expected."""
        assert state is None if expected is None else state

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == counts[0]
    assert_state(hass.states.get("device_tracker.ws_client_1"), expected[0][0])
    assert_state(hass.states.get("device_tracker.wd_client_1"), expected[0][1])
    assert_state(hass.states.get("device_tracker.switch_1"), expected[0][2])

    # Keep only the primary option and turn it off, everything else uses default
    hass.config_entries.async_update_entry(config_entry_setup, options={option: False})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == counts[1]
    assert_state(hass.states.get("device_tracker.ws_client_1"), expected[1][0])
    assert_state(hass.states.get("device_tracker.wd_client_1"), expected[1][1])
    assert_state(hass.states.get("device_tracker.switch_1"), expected[1][2])

    # Turn on the primary option, everything else uses default
    hass.config_entries.async_update_entry(config_entry_setup, options={option: True})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3
    assert_state(hass.states.get("device_tracker.ws_client_1"), True)
    assert_state(hass.states.get("device_tracker.wd_client_1"), True)
    assert_state(hass.states.get("device_tracker.switch_1"), True)
