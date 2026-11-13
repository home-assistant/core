"""Test songpal media_player."""

import asyncio
from datetime import timedelta
import logging
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from async_upnp_client.exceptions import (
    UpnpActionResponseError,
    UpnpConnectionTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from songpal import (
    ConnectChange,
    ContentChange,
    PowerChange,
    SongpalException,
    VolumeChange,
)
from songpal.group import GroupState
from songpal.notification import SettingChange

from homeassistant.components import media_player, songpal
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.songpal.const import ERROR_REQUEST_RETRY
from homeassistant.components.songpal.media_player import GROUP_ENTITIES
from homeassistant.components.songpal.services import SongpalService
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    CONF_DATA,
    CONF_ENDPOINT,
    CONF_NAME,
    ENDPOINT,
    ENTITY_ID,
    FRIENDLY_NAME,
    HOST,
    LEADER_ENTITY_ID,
    LEADER_LOCATION,
    LEADER_UDN,
    MAC,
    MEMBER_ENTITY_ID,
    MEMBER_UDN,
    MODEL,
    SW_VERSION,
    WIRELESS_MAC,
    _create_mocked_device,
    _create_mocked_group_control,
    _group_state,
    _patch_media_player_device,
    _setup_songpal,
    _ssdp_info,
)

SUPPORT_SONGPAL = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


def _get_attributes(hass: HomeAssistant) -> dict[str, Any]:
    state = hass.states.get(ENTITY_ID)
    return state.as_dict()["attributes"]


async def _call(hass: HomeAssistant, service: str, **argv: Any) -> None:
    await hass.services.async_call(
        media_player.DOMAIN,
        service,
        {"entity_id": ENTITY_ID, **argv},
        blocking=True,
    )


async def test_setup_platform(hass: HomeAssistant) -> None:
    """Test the legacy setup platform."""
    mocked_device = _create_mocked_device(throw_exception=True)
    with _patch_media_player_device(mocked_device):
        await async_setup_component(
            hass,
            media_player.DOMAIN,
            {
                media_player.DOMAIN: [
                    {
                        "platform": songpal.DOMAIN,
                        CONF_NAME: FRIENDLY_NAME,
                        CONF_ENDPOINT: ENDPOINT,
                    }
                ],
            },
        )
        await hass.async_block_till_done()

    # No device is set up
    mocked_device.assert_not_called()
    all_states = hass.states.async_all()
    assert len(all_states) == 0


async def test_setup_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failed to set up the entity."""
    mocked_device = _create_mocked_device(throw_exception=True)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    all_states = hass.states.async_all()
    assert len(all_states) == 0
    assert "[name(http://0.0.0.0:10000/sony)] Unable to connect" in caplog.text
    assert "Platform songpal not ready yet: Unable to do POST request" in caplog.text
    assert not any(x.levelno == logging.ERROR for x in caplog.records)
    caplog.clear()

    utcnow = dt_util.utcnow()
    type(mocked_device).get_supported_methods = AsyncMock()
    with _patch_media_player_device(mocked_device):
        async_fire_time_changed(hass, utcnow + timedelta(seconds=30))
        await hass.async_block_till_done()
    all_states = hass.states.async_all()
    assert len(all_states) == 1
    assert not any(x.levelno == logging.WARNING for x in caplog.records)
    assert not any(x.levelno == logging.ERROR for x in caplog.records)


async def test_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test state of the entity."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    attributes = state.as_dict()["attributes"]
    assert attributes["volume_level"] == 0.5
    assert attributes["is_volume_muted"] is False
    assert attributes["source_list"] == ["title1", "title2"]
    assert attributes["source"] == "title2"
    assert attributes["sound_mode_list"] == ["Sound Mode 1", "Sound Mode 2"]
    assert attributes["sound_mode"] == "Sound Mode 2"
    assert attributes["supported_features"] == SUPPORT_SONGPAL

    device = device_registry.async_get_device_by_identifier(
        (songpal.DOMAIN, MAC), entry.entry_id
    )
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert device.manufacturer == "Sony Corporation"
    assert device.name == FRIENDLY_NAME
    assert device.sw_version == SW_VERSION
    assert device.model == MODEL

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == MAC


async def test_state_nosoundmode(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test state of the entity with no soundField in sound settings."""
    mocked_device = _create_mocked_device(no_soundfield=True)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    attributes = state.as_dict()["attributes"]
    assert attributes["volume_level"] == 0.5
    assert attributes["is_volume_muted"] is False
    assert attributes["source_list"] == ["title1", "title2"]
    assert attributes["source"] == "title2"
    assert "sound_mode_list" not in attributes
    assert "sound_mode" not in attributes
    assert attributes["supported_features"] == SUPPORT_SONGPAL

    device = device_registry.async_get_device_by_identifier(
        (songpal.DOMAIN, MAC), entry.entry_id
    )
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert device.manufacturer == "Sony Corporation"
    assert device.name == FRIENDLY_NAME
    assert device.sw_version == SW_VERSION
    assert device.model == MODEL

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == MAC


async def test_state_wireless(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test state of the entity with only Wireless MAC."""
    mocked_device = _create_mocked_device(wired_mac=None, wireless_mac=WIRELESS_MAC)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    attributes = state.as_dict()["attributes"]
    assert attributes["volume_level"] == 0.5
    assert attributes["is_volume_muted"] is False
    assert attributes["source_list"] == ["title1", "title2"]
    assert attributes["source"] == "title2"
    assert attributes["sound_mode_list"] == ["Sound Mode 1", "Sound Mode 2"]
    assert attributes["sound_mode"] == "Sound Mode 2"
    assert attributes["supported_features"] == SUPPORT_SONGPAL

    device = device_registry.async_get_device_by_identifier(
        (songpal.DOMAIN, WIRELESS_MAC), entry.entry_id
    )
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, WIRELESS_MAC)}
    assert device.manufacturer == "Sony Corporation"
    assert device.name == FRIENDLY_NAME
    assert device.sw_version == SW_VERSION
    assert device.model == MODEL

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == WIRELESS_MAC


async def test_state_both(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test state of the entity with both Wired and Wireless MAC."""
    mocked_device = _create_mocked_device(wired_mac=MAC, wireless_mac=WIRELESS_MAC)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    attributes = state.as_dict()["attributes"]
    assert attributes["volume_level"] == 0.5
    assert attributes["is_volume_muted"] is False
    assert attributes["source_list"] == ["title1", "title2"]
    assert attributes["source"] == "title2"
    assert attributes["sound_mode_list"] == ["Sound Mode 1", "Sound Mode 2"]
    assert attributes["sound_mode"] == "Sound Mode 2"
    assert attributes["supported_features"] == SUPPORT_SONGPAL

    device = device_registry.async_get_device_by_identifier(
        (songpal.DOMAIN, MAC), entry.entry_id
    )
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, MAC),
        (dr.CONNECTION_NETWORK_MAC, WIRELESS_MAC),
    }
    assert device.manufacturer == "Sony Corporation"
    assert device.name == FRIENDLY_NAME
    assert device.sw_version == SW_VERSION
    assert device.model == MODEL

    entity = entity_registry.async_get(ENTITY_ID)
    # We prefer the wired mac if present.
    assert entity.unique_id == MAC


async def test_services(hass: HomeAssistant) -> None:
    """Test services."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await _call(hass, media_player.SERVICE_TURN_ON)
    await _call(hass, media_player.SERVICE_TURN_OFF)
    await _call(hass, media_player.SERVICE_TOGGLE)
    assert mocked_device.set_power.call_count == 3
    mocked_device.set_power.assert_has_calls([call(True), call(False), call(False)])

    await _call(hass, media_player.SERVICE_VOLUME_SET, volume_level=0.6)
    await _call(hass, media_player.SERVICE_VOLUME_UP)
    await _call(hass, media_player.SERVICE_VOLUME_DOWN)
    assert mocked_device.volume1.set_volume.call_count == 3
    mocked_device.volume1.set_volume.assert_has_calls([call(60), call(51), call(49)])

    await _call(hass, media_player.SERVICE_VOLUME_MUTE, is_volume_muted=True)
    mocked_device.volume1.set_mute.assert_called_once_with(True)

    await _call(hass, media_player.SERVICE_SELECT_SOURCE, source="none")
    mocked_device.input1.activate.assert_not_called()
    await _call(hass, media_player.SERVICE_SELECT_SOURCE, source="title1")
    mocked_device.input1.activate.assert_called_once()

    await hass.services.async_call(
        songpal.DOMAIN,
        SongpalService.SET_SOUND_SETTING,
        {"entity_id": ENTITY_ID, "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device.set_sound_settings.reset_mock()

    mocked_device2 = _create_mocked_device(wired_mac="mac2")
    entry2 = MockConfigEntry(
        domain=songpal.DOMAIN, data={CONF_NAME: "d2", CONF_ENDPOINT: ENDPOINT}
    )
    entry2.add_to_hass(hass)
    with _patch_media_player_device(mocked_device2):
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        songpal.DOMAIN,
        SongpalService.SET_SOUND_SETTING,
        {"entity_id": "all", "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device2.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device.set_sound_settings.reset_mock()
    mocked_device2.set_sound_settings.reset_mock()

    mocked_device3 = _create_mocked_device(wired_mac=None, wireless_mac=WIRELESS_MAC)
    entry3 = MockConfigEntry(
        domain=songpal.DOMAIN, data={CONF_NAME: "d2", CONF_ENDPOINT: ENDPOINT}
    )
    entry3.add_to_hass(hass)
    with _patch_media_player_device(mocked_device3):
        await hass.config_entries.async_setup(entry3.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        songpal.DOMAIN,
        SongpalService.SET_SOUND_SETTING,
        {"entity_id": "all", "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device2.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device3.set_sound_settings.assert_called_once_with("name", "value")

    await _call(hass, media_player.SERVICE_SELECT_SOUND_MODE, sound_mode="Sound Mode 1")
    mocked_device.set_sound_settings.assert_called_with("soundField", "sound_mode1")


async def test_websocket_events(hass: HomeAssistant) -> None:
    """Test websocket events."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mocked_device.listen_notifications.assert_called_once()
    assert mocked_device.on_notification.call_count == 5

    notification_callbacks = mocked_device.notification_callbacks

    volume_change = MagicMock()
    volume_change.mute = True
    volume_change.volume = 20
    await notification_callbacks[VolumeChange](volume_change)
    attributes = _get_attributes(hass)
    assert attributes["is_volume_muted"] is True
    assert attributes["volume_level"] == 0.2

    content_change = MagicMock()
    content_change.is_input = False
    content_change.uri = "uri1"
    await notification_callbacks[ContentChange](content_change)
    assert _get_attributes(hass)["source"] == "title2"
    content_change.is_input = True
    await notification_callbacks[ContentChange](content_change)
    assert _get_attributes(hass)["source"] == "title1"

    sound_mode_change = MagicMock()
    sound_mode_change.target = "soundField"
    sound_mode_change.currentValue = "sound_mode1"
    await notification_callbacks[SettingChange](sound_mode_change)
    assert _get_attributes(hass)["sound_mode"] == "Sound Mode 1"
    sound_mode_change.currentValue = "sound_mode2"
    await notification_callbacks[SettingChange](sound_mode_change)
    assert _get_attributes(hass)["sound_mode"] == "Sound Mode 2"

    power_change = MagicMock()
    power_change.status = False
    await notification_callbacks[PowerChange](power_change)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_stop_listener_removed_on_unload(hass: HomeAssistant) -> None:
    """Test the stop listener is removed when the entity is removed."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    stop_listeners = hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STOP]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STOP] == stop_listeners - 1


async def test_disconnected(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test disconnected behavior."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async def _assert_state():
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNAVAILABLE

    connect_change = MagicMock()
    connect_change.exception = "disconnected"
    type(mocked_device).get_supported_methods = AsyncMock(
        side_effect=[SongpalException(""), SongpalException(""), _assert_state]
    )
    notification_callbacks = mocked_device.notification_callbacks
    with patch("homeassistant.components.songpal.media_player.INITIAL_RETRY_DELAY", 0):
        await notification_callbacks[ConnectChange](connect_change)
    warning_records = [x for x in caplog.records if x.levelno == logging.WARNING]
    assert len(warning_records) == 2
    assert warning_records[0].message.endswith("Got disconnected, trying to reconnect")
    assert warning_records[1].message.endswith("Connection reestablished")
    assert not any(x.levelno == logging.ERROR for x in caplog.records)


@pytest.mark.parametrize(
    "service", [media_player.SERVICE_TURN_ON, media_player.SERVICE_TURN_OFF]
)
@pytest.mark.parametrize(
    ("error_code", "swallow"), [(ERROR_REQUEST_RETRY, True), (1234, False)]
)
async def test_error_swallowing(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, service, error_code, swallow
) -> None:
    """Test swallowing specific errors on turn_on and turn_off."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    type(mocked_device).set_power = AsyncMock(
        side_effect=[
            SongpalException("Error to swallow", error=(error_code, "Error to swallow"))
        ]
    )

    if swallow:
        await _call(hass, service)
        assert "Swallowing" in caplog.text
    else:
        with pytest.raises(SongpalException):
            await _call(hass, service)


@pytest.mark.parametrize(
    ("max_volume", "volume", "service", "expected_volume"),
    [
        pytest.param(95, 28, media_player.SERVICE_VOLUME_UP, 29, id="up_max_95"),
        pytest.param(14, 4, media_player.SERVICE_VOLUME_UP, 5, id="up_max_14"),
        pytest.param(95, 30, media_player.SERVICE_VOLUME_DOWN, 29, id="down_max_95"),
    ],
)
async def test_volume_step(
    hass: HomeAssistant,
    max_volume: int,
    volume: int,
    service: str,
    expected_volume: int,
) -> None:
    """Test a volume step moves exactly one device volume step."""
    mocked_device = _create_mocked_device()
    mocked_device.volume1.maxVolume = max_volume
    mocked_device.volume1.volume = volume
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await _call(hass, service)
    mocked_device.volume1.set_volume.assert_called_once_with(expected_volume)


OTHER_LOCATION = f"http://{HOST}:54381/other.xml"
DMR_LOCATION = f"http://{HOST}:54380/dmr.xml"
HOST_NAME_ENDPOINT = "http://soundbar.local:10000/sony"

with_grouping_mocks = pytest.mark.usefixtures(
    "mock_devices", "mock_group_controls", "mock_ssdp"
)


def _assert_group_created(group_control: MagicMock, name: str) -> None:
    group_control.call.assert_called_once_with(
        "X_Start",
        GroupMode="GROUP",
        GroupName=name,
        SlaveList=MEMBER_UDN,
        CodecType=48,
        CodecBitrate=0,
    )


def _assert_no_group_created(group_control: MagicMock) -> None:
    assert all(call.args[0] != "X_Start" for call in group_control.call.call_args_list)


def _group_members(hass: HomeAssistant, entity_id: str) -> list[str] | None:
    return hass.states.get(entity_id).attributes.get(media_player.ATTR_GROUP_MEMBERS)


def _supported_features(hass: HomeAssistant, entity_id: str = ENTITY_ID) -> int:
    return hass.states.get(entity_id).attributes[ATTR_SUPPORTED_FEATURES]


async def _join(hass: HomeAssistant, entity_id: str, members: list[str]) -> None:
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_JOIN,
        {"entity_id": entity_id, media_player.ATTR_GROUP_MEMBERS: members},
        blocking=True,
    )


async def _unjoin(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_UNJOIN,
        {"entity_id": entity_id},
        blocking=True,
    )


async def _disconnect(hass: HomeAssistant, device: MagicMock) -> None:
    connect_change = MagicMock()
    connect_change.exception = "disconnected"
    with patch("homeassistant.components.songpal.media_player.INITIAL_RETRY_DELAY", 0):
        await device.notification_callbacks[ConnectChange](connect_change)
        await hass.async_block_till_done(wait_background_tasks=True)


async def _fire_poll(hass: HomeAssistant, seconds: float = 31) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


GROUPED = [LEADER_ENTITY_ID, MEMBER_ENTITY_ID]
LEADER_GROUP = _group_state("GROUP", member_udns=MEMBER_UDN)
MEMBER_GROUP = _group_state("GROUP", leader_udn=LEADER_UDN)


@with_grouping_mocks
async def test_grouping_not_supported_without_ssdp_info(
    hass: HomeAssistant,
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test grouping is not offered when the device was not discovered."""
    mock_ssdp.append(_ssdp_info(LEADER_LOCATION, LEADER_UDN))

    await _setup_songpal(hass)

    assert not mock_group_controls
    assert _supported_features(hass) == SUPPORT_SONGPAL
    assert _group_members(hass, ENTITY_ID) is None


@with_grouping_mocks
async def test_grouping_group_service_missing(
    hass: HomeAssistant,
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test grouping is not offered when the device has no group service."""
    group_control = mock_group_controls[DMR_LOCATION] = _create_mocked_group_control(
        _group_state()
    )
    group_control.connect.return_value = False
    mock_ssdp.append(_ssdp_info(DMR_LOCATION, LEADER_UDN))

    await _setup_songpal(hass)

    group_control.connect.assert_called_once()
    assert _supported_features(hass) == SUPPORT_SONGPAL


@with_grouping_mocks
async def test_group_setup_retried(
    hass: HomeAssistant,
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test connecting to the group service is retried while polling."""
    group_control = mock_group_controls[DMR_LOCATION] = _create_mocked_group_control(
        _group_state()
    )
    group_control.connect.side_effect = [TimeoutError, True]
    mock_ssdp.append(_ssdp_info(DMR_LOCATION, LEADER_UDN))

    await _setup_songpal(hass)
    assert _supported_features(hass) == SUPPORT_SONGPAL

    await _fire_poll(hass)

    assert (
        _supported_features(hass) == SUPPORT_SONGPAL | MediaPlayerEntityFeature.GROUPING
    )
    assert _group_members(hass, ENTITY_ID) == [ENTITY_ID]


@pytest.mark.parametrize(
    ("base_url", "getaddrinfo", "grouping"),
    [
        pytest.param(HOST_NAME_ENDPOINT, AsyncMock(), True, id="reported_endpoint"),
        pytest.param(
            None,
            AsyncMock(
                return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))
                ]
            ),
            True,
            id="resolved_host_name",
        ),
        pytest.param(
            None, AsyncMock(side_effect=socket.gaierror), False, id="unresolved"
        ),
    ],
)
@with_grouping_mocks
async def test_group_setup_host_name_endpoint(
    hass: HomeAssistant,
    mock_ssdp: list[SsdpServiceInfo],
    base_url: str | None,
    getaddrinfo: AsyncMock,
    grouping: bool,
) -> None:
    """Test the SSDP discovery of an endpoint with a host name is matched."""
    mock_ssdp.extend(
        [
            _ssdp_info("http://10.0.0.9:80/description.xml", "uuid:other"),
            _ssdp_info(LEADER_LOCATION, LEADER_UDN, base_url=base_url),
        ]
    )

    with patch.object(hass.loop, "getaddrinfo", getaddrinfo):
        await _setup_songpal(hass, endpoint=HOST_NAME_ENDPOINT)

    # The host name is only resolved when the reported endpoint doesn't match
    assert getaddrinfo.called is (base_url is None)
    expected = SUPPORT_SONGPAL | (MediaPlayerEntityFeature.GROUPING if grouping else 0)
    assert _supported_features(hass) == expected


async def test_group_members(hass: HomeAssistant, mock_group) -> None:
    """Test the group members of ungrouped devices."""
    assert _supported_features(hass, LEADER_ENTITY_ID) == (
        SUPPORT_SONGPAL | MediaPlayerEntityFeature.GROUPING
    )
    assert _group_members(hass, LEADER_ENTITY_ID) == [LEADER_ENTITY_ID]
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


@pytest.mark.parametrize(
    "leader_state", [_group_state("GROUP", member_udns=f"{MEMBER_UDN},uuid:unknown")]
)
@pytest.mark.parametrize("member_state", [MEMBER_GROUP])
async def test_group_members_grouped(hass: HomeAssistant, mock_group) -> None:
    """Test the group members of an existing group, leader first."""
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED
    assert _group_members(hass, MEMBER_ENTITY_ID) == GROUPED


@pytest.mark.parametrize("member_state", [_group_state("GROUP", leader_udn="uuid:x")])
async def test_group_members_unknown_leader(hass: HomeAssistant, mock_group) -> None:
    """Test a member of a group led by a device unknown to Home Assistant."""
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


async def test_group_state_polling(hass: HomeAssistant, mock_group) -> None:
    """Test group changes made outside Home Assistant are picked up."""
    leader, member = mock_group
    leader.state.return_value = LEADER_GROUP
    member.state.return_value = MEMBER_GROUP

    await _fire_poll(hass)

    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED
    assert _group_members(hass, MEMBER_ENTITY_ID) == GROUPED

    # The last known group is kept while the group service does not respond
    leader.state.side_effect = UpnpConnectionTimeoutError
    await _fire_poll(hass, 62)

    leader.state.assert_called()
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED


async def test_join_creates_group(hass: HomeAssistant, mock_group) -> None:
    """Test joining ungrouped devices creates a new group, shown immediately."""
    leader, member = mock_group

    await _join(hass, LEADER_ENTITY_ID, GROUPED)

    _assert_group_created(leader, "Living room + Bathroom")
    _assert_no_group_created(member)
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED
    assert _group_members(hass, MEMBER_ENTITY_ID) == GROUPED

    # The devices confirm the group once they have settled
    leader.state.reset_mock()
    leader.state.return_value = LEADER_GROUP
    member.state.return_value = MEMBER_GROUP
    await _fire_poll(hass, 3)

    leader.state.assert_called_once()
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED
    assert _group_members(hass, MEMBER_ENTITY_ID) == GROUPED


async def test_join_corrected_when_not_grouped(hass: HomeAssistant, mock_group) -> None:
    """Test the expected group is corrected if the devices did not group."""
    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])
    assert _group_members(hass, MEMBER_ENTITY_ID) == GROUPED

    await _fire_poll(hass, 3)

    assert _group_members(hass, LEADER_ENTITY_ID) == [LEADER_ENTITY_ID]
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


async def test_poll_skipped_while_settling(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_group
) -> None:
    """Test polling does not overwrite the expected group before it is verified."""
    leader, member = mock_group
    freezer.tick(timedelta(seconds=29))
    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])
    leader.state.reset_mock()
    member.state.reset_mock()

    # The regular poll is due while the devices still report no group
    freezer.tick(timedelta(seconds=1.2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    leader.state.assert_not_called()
    member.state.assert_not_called()
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    leader.state.assert_called_once()
    member.state.assert_called_once()


@pytest.mark.parametrize("leader_state", [_group_state("GROUP", member_udns="uuid:x")])
async def test_join_adds_to_existing_group(hass: HomeAssistant, mock_group) -> None:
    """Test joining when already leading a group adds only new members."""
    leader, _ = mock_group

    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])

    leader.add.assert_called_once_with(MEMBER_UDN)
    _assert_no_group_created(leader)
    # Members unknown to Home Assistant are left out of the name
    leader.set_group_name.assert_called_once_with("Living room + Bathroom")

    leader.add.reset_mock()
    leader.state.return_value = LEADER_GROUP
    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])
    leader.add.assert_not_called()


async def test_join_only_self(hass: HomeAssistant, mock_group) -> None:
    """Test joining only the leader itself does nothing."""
    leader, _ = mock_group

    await _join(hass, LEADER_ENTITY_ID, [LEADER_ENTITY_ID])

    leader.state.assert_called_once()
    _assert_no_group_created(leader)


async def test_join_unsupported_member(hass: HomeAssistant, mock_group) -> None:
    """Test joining a device not supporting grouping fails."""
    leader, _ = mock_group

    with pytest.raises(ServiceValidationError) as exc_info:
        await _join(hass, LEADER_ENTITY_ID, ["media_player.other"])

    assert exc_info.value.translation_key == "group_member_not_supported"
    _assert_no_group_created(leader)


@pytest.mark.parametrize("member_state", [_group_state("GROUP", leader_udn="uuid:x")])
async def test_join_while_member_of_other_group(
    hass: HomeAssistant, mock_group
) -> None:
    """Test a group member cannot lead a group."""
    _, member = mock_group

    with pytest.raises(ServiceValidationError) as exc_info:
        await _join(hass, MEMBER_ENTITY_ID, [LEADER_ENTITY_ID])

    assert exc_info.value.translation_key == "group_member_of_other_group"
    _assert_no_group_created(member)


async def test_join_failed(hass: HomeAssistant, mock_group) -> None:
    """Test errors of the group service are raised."""
    leader, _ = mock_group
    leader.call.side_effect = UpnpActionResponseError(status=500)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])

    assert exc_info.value.translation_key == "grouping_failed"


@pytest.mark.parametrize("leader_state", [LEADER_GROUP])
@pytest.mark.parametrize("member_state", [MEMBER_GROUP])
async def test_unjoin_leader(hass: HomeAssistant, mock_group) -> None:
    """Test unjoining the leader dissolves the group."""
    leader, _ = mock_group

    await _unjoin(hass, LEADER_ENTITY_ID)

    leader.abort.assert_called_once()
    assert _group_members(hass, LEADER_ENTITY_ID) == [LEADER_ENTITY_ID]
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


@pytest.mark.parametrize("leader_state", [LEADER_GROUP])
@pytest.mark.parametrize(
    "member_state", [_group_state("GROUP", leader_udn=LEADER_UDN, session=5)]
)
async def test_unjoin_member(hass: HomeAssistant, mock_group) -> None:
    """Test unjoining a member removes it through the leader."""
    leader, member = mock_group

    await _unjoin(hass, MEMBER_ENTITY_ID)

    leader.remove.assert_called_once_with(MEMBER_UDN)
    member.call.assert_not_called()
    member.abort.assert_not_called()
    assert _group_members(hass, LEADER_ENTITY_ID) == [LEADER_ENTITY_ID]
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


@pytest.mark.parametrize(
    "member_state", [_group_state("GROUP", leader_udn="uuid:x", session=5)]
)
async def test_unjoin_member_of_unknown_leader(hass: HomeAssistant, mock_group) -> None:
    """Test unjoining a member of a group led by an unknown device."""
    _, member = mock_group

    await _unjoin(hass, MEMBER_ENTITY_ID)

    member.call.assert_called_once_with("X_Exit", SlaveSessionID=5)


async def test_unjoin_ungrouped(hass: HomeAssistant, mock_group) -> None:
    """Test unjoining an ungrouped device does nothing."""
    leader, _ = mock_group

    await _unjoin(hass, LEADER_ENTITY_ID)

    leader.abort.assert_not_called()
    leader.remove.assert_not_called()


@pytest.mark.parametrize("leader_state", [LEADER_GROUP])
async def test_unjoin_failed(hass: HomeAssistant, mock_group) -> None:
    """Test errors of the group service are raised when unjoining."""
    leader, _ = mock_group
    leader.abort.side_effect = UpnpActionResponseError(status=500)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _unjoin(hass, LEADER_ENTITY_ID)

    assert exc_info.value.translation_key == "grouping_failed"


@pytest.mark.parametrize(
    "leader_state", [_group_state("GROUP", member_udns=f"{MEMBER_UDN},uuid:x")]
)
@pytest.mark.parametrize("member_state", [MEMBER_GROUP])
async def test_unjoin_member_renames_group(hass: HomeAssistant, mock_group) -> None:
    """Test the group is renamed when a member leaves and others remain."""
    leader, _ = mock_group

    await _unjoin(hass, MEMBER_ENTITY_ID)

    leader.remove.assert_called_once_with(MEMBER_UDN)
    leader.set_group_name.assert_called_once_with("Living room")
    assert _group_members(hass, MEMBER_ENTITY_ID) == [MEMBER_ENTITY_ID]


@pytest.mark.parametrize("leader_state", [_group_state("GROUP", member_udns="uuid:x")])
async def test_rename_failure_does_not_fail_join(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_group
) -> None:
    """Test a failed rename is logged, the join itself succeeded."""
    leader, _ = mock_group
    leader.set_group_name.side_effect = UpnpActionResponseError(status=500)

    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])

    leader.add.assert_called_once_with(MEMBER_UDN)
    assert "Unable to rename the group of media_player.leader" in caplog.text
    assert _group_members(hass, LEADER_ENTITY_ID) == GROUPED


@pytest.mark.parametrize(
    ("friendly_names", "leader_state", "expected_name"),
    [
        pytest.param(
            ("Living room", "Bathroom"),
            _group_state("GROUP", member_udns="uuid:a"),
            "Living room + Bathroom",
            id="three_listed",
        ),
        pytest.param(
            ("Living room", "Bathroom"),
            _group_state("GROUP", member_udns="uuid:a,uuid:b"),
            "Living room + 3",
            id="four_counted",
        ),
        pytest.param(
            ("L" * 40, "B" * 30), _group_state(), f"{'L' * 40} + 1", id="too_long"
        ),
        pytest.param(("Ä" * 40, "Bathroom"), _group_state(), "Ä" * 32, id="truncated"),
        pytest.param(
            (None, None), _group_state(), "leader + member", id="config_names"
        ),
    ],
)
async def test_group_name(
    hass: HomeAssistant,
    mock_group,
    leader_state: GroupState,
    expected_name: str,
) -> None:
    """Test the group name lists the devices, or counts them for large groups."""
    leader, _ = mock_group

    await _join(hass, LEADER_ENTITY_ID, [MEMBER_ENTITY_ID])

    if leader_state.GroupMode == "GROUP":
        leader.set_group_name.assert_called_once_with(expected_name)
    else:
        _assert_group_created(leader, expected_name)
    assert len(expected_name.encode()) <= 64


async def test_group_control_rediscovered_after_reconnect(
    hass: HomeAssistant,
    mock_devices: dict[str, MagicMock],
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test the group service is looked up again after a reconnect."""
    mock_ssdp.append(_ssdp_info(DMR_LOCATION, LEADER_UDN, base_url=ENDPOINT))
    await _setup_songpal(hass)
    old_group_control = mock_group_controls[DMR_LOCATION]
    old_group_control.state.reset_mock()

    mock_ssdp[:] = [_ssdp_info(OTHER_LOCATION, LEADER_UDN, base_url=ENDPOINT)]
    await _disconnect(hass, mock_devices[ENDPOINT])

    new_group_control = mock_group_controls[OTHER_LOCATION]
    new_group_control.connect.assert_called_once()
    await _fire_poll(hass)
    new_group_control.state.assert_called_once()
    old_group_control.state.assert_not_called()


async def test_reconnect_stops_when_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_devices: dict[str, MagicMock],
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test a removed entity stops reconnecting and is not set up again."""
    mock_ssdp.append(_ssdp_info(DMR_LOCATION, LEADER_UDN, base_url=ENDPOINT))
    await _setup_songpal(hass)
    device = mock_devices[ENDPOINT]
    listen_calls = device.listen_notifications.call_count
    device.get_supported_methods.side_effect = SongpalException("Unreachable")

    reconnect = hass.async_create_task(_disconnect(hass, device))
    await asyncio.sleep(0)
    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert reconnect.done()
    assert device.listen_notifications.call_count == listen_calls
    mock_group_controls[DMR_LOCATION].connect.assert_called_once()


async def test_group_setup_skipped_when_removed_while_connecting(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_devices: dict[str, MagicMock],
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
) -> None:
    """Test an entity removed while connecting to the group service isn't kept."""
    mock_ssdp.append(_ssdp_info(DMR_LOCATION, LEADER_UDN, base_url=ENDPOINT))
    await _setup_songpal(hass)
    assert LEADER_UDN in hass.data[GROUP_ENTITIES]

    async def _connect() -> bool:
        entity_registry.async_remove(ENTITY_ID)
        await hass.async_block_till_done()
        return True

    new_group_control = mock_group_controls[OTHER_LOCATION] = (
        _create_mocked_group_control(_group_state())
    )
    new_group_control.connect.side_effect = _connect
    mock_ssdp[:] = [_ssdp_info(OTHER_LOCATION, LEADER_UDN, base_url=ENDPOINT)]
    await _disconnect(hass, mock_devices[ENDPOINT])

    new_group_control.connect.assert_called_once()
    assert LEADER_UDN not in hass.data[GROUP_ENTITIES]
