"""Tests for the DLNA DMR media_player module."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from unittest.mock import ANY, DEFAULT, Mock, patch

from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.exceptions import (
    UpnpConnectionError,
    UpnpError,
    UpnpResponseError,
)
from async_upnp_client.profiles.dlna import PlayMode, TransportState
from didl_lite import didl_lite
import pytest

from homeassistant import const as ha_const
from homeassistant.components import media_player as mp, ssdp
from homeassistant.components.dlna_dmr.const import (
    CONF_BROWSE_UNFILTERED,
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN,
)
from homeassistant.components.dlna_dmr.data import EventListenAddr
from homeassistant.components.dlna_dmr.media_player import DlnaDmrEntity
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_source import DOMAIN as MS_DOMAIN, PlayMedia
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_MAC,
    CONF_TYPE,
    CONF_URL,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import (
    LOCAL_IP,
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_UDN,
    MOCK_DEVICE_USN,
    MOCK_MAC_ADDRESS,
    NEW_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

# Auto-use the domain_data_mock fixture for every test in this module
pytestmark = pytest.mark.usefixtures("domain_data_mock")


async def setup_mock_component(hass: HomeAssistant, mock_entry: MockConfigEntry) -> str:
    """Set up a mock DlnaDmrEntity with the given configuration."""
    assert await hass.config_entries.async_setup(mock_entry.entry_id) is True
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
    assert len(entries) == 1
    return entries[0].entity_id


async def get_attrs(hass: HomeAssistant, entity_id: str) -> Mapping[str, Any]:
    """Get updated device attributes."""
    await async_update_entity(hass, entity_id)
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    attrs = entity_state.attributes
    assert attrs is not None
    return attrs


@pytest.fixture
async def mock_entity_id(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
) -> AsyncGenerator[str]:
    """Fixture to set up a mock DlnaDmrEntity in a connected state.

    Yields the entity ID. Cleans up the entity after the test is complete.
    """
    config_entry_mock.add_to_hass(hass)
    entity_id = await setup_mock_component(hass, config_entry_mock)

    # Check the entity has registered all needed listeners
    assert len(config_entry_mock.update_listeners) == 1
    assert domain_data_mock.async_get_event_notifier.await_count == 1
    assert domain_data_mock.async_release_event_notifier.await_count == 0
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1
    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.on_event is not None

    # Run the test
    yield entity_id

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check entity has cleaned up its resources
    assert not config_entry_mock.update_listeners
    assert (
        domain_data_mock.async_get_event_notifier.await_count
        == domain_data_mock.async_release_event_notifier.await_count
    )
    assert (
        ssdp_scanner_mock.async_register_callback.await_count
        == ssdp_scanner_mock.async_register_callback.return_value.call_count
    )
    assert (
        dmr_device_mock.async_subscribe_services.await_count
        == dmr_device_mock.async_unsubscribe_services.await_count
    )
    assert dmr_device_mock.on_event is None


@pytest.fixture
async def mock_disconnected_entity_id(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
) -> AsyncGenerator[str]:
    """Fixture to set up a mock DlnaDmrEntity in a disconnected state.

    Yields the entity ID. Cleans up the entity after the test is complete.
    """
    # Cause the connection attempt to fail
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    entity_id = await setup_mock_component(hass, config_entry_mock)

    # Check the entity has registered all needed listeners
    assert len(config_entry_mock.update_listeners) == 1
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0

    # The DmrDevice hasn't been instantiated yet
    assert domain_data_mock.async_get_event_notifier.await_count == 0
    assert domain_data_mock.async_release_event_notifier.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 0
    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.on_event is None

    # Run the test
    yield entity_id

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check entity has cleaned up its resources
    assert not config_entry_mock.update_listeners
    assert (
        domain_data_mock.async_get_event_notifier.await_count
        == domain_data_mock.async_release_event_notifier.await_count
    )
    assert (
        ssdp_scanner_mock.async_register_callback.await_count
        == ssdp_scanner_mock.async_register_callback.return_value.call_count
    )
    assert (
        dmr_device_mock.async_subscribe_services.await_count
        == dmr_device_mock.async_unsubscribe_services.await_count
    )
    assert dmr_device_mock.on_event is None


async def test_setup_entry_no_options(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test async_setup_entry creates a DlnaDmrEntity when no options are set.

    Check that the device is constructed properly as part of the test.
    """
    config_entry_mock.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry_mock, options={})
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    # Check event notifiers are acquired
    domain_data_mock.async_get_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None), hass
    )
    # Check UPnP services are subscribed
    dmr_device_mock.async_subscribe_services.assert_awaited_once_with(
        auto_resubscribe=True
    )
    assert dmr_device_mock.on_event is not None
    # Check SSDP notifications are registered
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"USN": MOCK_DEVICE_USN}
    )
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"_udn": MOCK_DEVICE_UDN, "NTS": "ssdp:byebye"}
    )
    # Quick check of the state to verify the entity has a connected DmrDevice
    assert mock_state.state == MediaPlayerState.IDLE
    # Check the name matches that supplied
    assert mock_state.name == MOCK_DEVICE_NAME

    # Check that an update retrieves state from the device, but does not ping,
    # because poll_availability is False
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_awaited_with(do_ping=False)

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Confirm the entity has disconnected from the device
    domain_data_mock.async_release_event_notifier.assert_awaited_once()
    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()
    assert dmr_device_mock.on_event is None
    # Entity should be removed by the cleanup
    assert hass.states.get(mock_entity_id) is None


@pytest.mark.parametrize(
    "core_state",
    [CoreState.not_running, CoreState.running],
)
async def test_setup_entry_with_options(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    core_state: CoreState,
) -> None:
    """Test setting options leads to a DlnaDmrEntity with custom event_handler.

    Check that the device is constructed properly as part of the test.
    """
    hass.set_state(core_state)
    config_entry_mock.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://198.51.100.10/events",
            CONF_POLL_AVAILABILITY: True,
        },
    )
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    # Check event notifiers are acquired with the configured port and callback URL
    domain_data_mock.async_get_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 2222, "http://198.51.100.10/events"), hass
    )
    # Check UPnP services are subscribed
    dmr_device_mock.async_subscribe_services.assert_awaited_once_with(
        auto_resubscribe=True
    )
    assert dmr_device_mock.on_event is not None
    # Check SSDP notifications are registered
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"USN": MOCK_DEVICE_USN}
    )
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"_udn": MOCK_DEVICE_UDN, "NTS": "ssdp:byebye"}
    )
    # Quick check of the state to verify the entity has a connected DmrDevice
    assert mock_state.state == MediaPlayerState.IDLE
    # Check the name matches that supplied
    assert mock_state.name == MOCK_DEVICE_NAME

    # Check that an update retrieves state from the device, and also pings it,
    # because poll_availability is True
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_awaited_with(do_ping=True)

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Confirm the entity has disconnected from the device
    domain_data_mock.async_release_event_notifier.assert_awaited_once()
    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()
    assert dmr_device_mock.on_event is None
    # Entity should be removed by the cleanup
    assert hass.states.get(mock_entity_id) is None


async def test_setup_entry_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
) -> None:
    """Entry with a MAC address will set up and set the device registry connection."""
    config_entry_mock.add_to_hass(hass)
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    # Check the device registry connections for MAC address
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, MOCK_MAC_ADDRESS) in device.connections


async def test_setup_entry_no_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain_data_mock: Mock,
    config_entry_mock_no_mac: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
) -> None:
    """Test setting up an entry without a MAC address will succeed."""
    config_entry_mock_no_mac.add_to_hass(hass)
    mock_entity_id = await setup_mock_component(hass, config_entry_mock_no_mac)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    # Check the device registry connections does not include the MAC address
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, MOCK_MAC_ADDRESS) not in device.connections


async def test_event_subscribe_failure(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry, dmr_device_mock: Mock
) -> None:
    """Test _device_connect aborts when async_subscribe_services fails."""
    dmr_device_mock.async_subscribe_services.side_effect = UpnpError
    config_entry_mock.add_to_hass(hass)
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Device should not be connected
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Device should not be unsubscribed
    dmr_device_mock.async_unsubscribe_services.assert_not_awaited()

    # Clear mocks for tear down checks
    dmr_device_mock.async_subscribe_services.reset_mock()

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


async def test_event_subscribe_rejected(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test _device_connect continues when the device rejects a subscription.

    Device state will instead be obtained via polling in async_update.
    """
    dmr_device_mock.async_subscribe_services.side_effect = UpnpResponseError(status=501)
    config_entry_mock.add_to_hass(hass)

    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Device should be connected
    assert mock_state.state == MediaPlayerState.IDLE

    # Device should not be unsubscribed
    dmr_device_mock.async_unsubscribe_services.assert_not_awaited()

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


async def test_available_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test a DlnaDmrEntity with a connected DmrDevice."""
    # Check hass device information is filled in
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    # Device properties are set in dmr_device_mock before the entity gets constructed
    assert device.manufacturer == "device_manufacturer"
    assert device.model == "device_model_name"
    assert device.name == "device_name"

    # Check entity state gets updated when device changes state
    for dev_state, ent_state in (
        (None, MediaPlayerState.ON),
        (TransportState.STOPPED, MediaPlayerState.IDLE),
        (TransportState.PLAYING, MediaPlayerState.PLAYING),
        (TransportState.TRANSITIONING, MediaPlayerState.PLAYING),
        (TransportState.PAUSED_PLAYBACK, MediaPlayerState.PAUSED),
        (TransportState.PAUSED_RECORDING, MediaPlayerState.PAUSED),
        (TransportState.RECORDING, MediaPlayerState.IDLE),
        (TransportState.NO_MEDIA_PRESENT, MediaPlayerState.IDLE),
        (TransportState.VENDOR_DEFINED, ha_const.STATE_UNKNOWN),
    ):
        dmr_device_mock.profile_device.available = True
        dmr_device_mock.transport_state = dev_state
        await async_update_entity(hass, mock_entity_id)
        entity_state = hass.states.get(mock_entity_id)
        assert entity_state is not None
        assert entity_state.state == ent_state

    dmr_device_mock.profile_device.available = False
    dmr_device_mock.transport_state = TransportState.PLAYING
    await async_update_entity(hass, mock_entity_id)
    entity_state = hass.states.get(mock_entity_id)
    assert entity_state is not None
    assert entity_state.state == ha_const.STATE_UNAVAILABLE


async def test_feature_flags(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test feature flags of a connected DlnaDmrEntity."""
    # Check supported feature flags, one at a time.
    FEATURE_FLAGS: list[tuple[str, int]] = [
        ("has_volume_level", MediaPlayerEntityFeature.VOLUME_SET),
        ("has_volume_mute", MediaPlayerEntityFeature.VOLUME_MUTE),
        ("can_play", MediaPlayerEntityFeature.PLAY),
        ("can_pause", MediaPlayerEntityFeature.PAUSE),
        ("can_stop", MediaPlayerEntityFeature.STOP),
        ("can_previous", MediaPlayerEntityFeature.PREVIOUS_TRACK),
        ("can_next", MediaPlayerEntityFeature.NEXT_TRACK),
        (
            "has_play_media",
            MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.BROWSE_MEDIA,
        ),
        ("can_seek_rel_time", MediaPlayerEntityFeature.SEEK),
        ("has_presets", MediaPlayerEntityFeature.SELECT_SOUND_MODE),
    ]

    # Clear all feature properties
    dmr_device_mock.valid_play_modes = set()
    for feat_prop, _ in FEATURE_FLAGS:
        setattr(dmr_device_mock, feat_prop, False)
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[ha_const.ATTR_SUPPORTED_FEATURES] == 0

    # Test the properties cumulatively
    expected_features = 0
    for feat_prop, flag in FEATURE_FLAGS:
        setattr(dmr_device_mock, feat_prop, True)
        expected_features |= flag
        attrs = await get_attrs(hass, mock_entity_id)
        assert attrs[ha_const.ATTR_SUPPORTED_FEATURES] == expected_features

    # shuffle and repeat features depend on the available play modes
    PLAY_MODE_FEATURE_FLAGS: list[tuple[PlayMode, int]] = [
        (PlayMode.NORMAL, 0),
        (PlayMode.SHUFFLE, MediaPlayerEntityFeature.SHUFFLE_SET),
        (PlayMode.REPEAT_ONE, MediaPlayerEntityFeature.REPEAT_SET),
        (PlayMode.REPEAT_ALL, MediaPlayerEntityFeature.REPEAT_SET),
        (PlayMode.RANDOM, MediaPlayerEntityFeature.SHUFFLE_SET),
        (PlayMode.DIRECT_1, 0),
        (PlayMode.INTRO, 0),
        (PlayMode.VENDOR_DEFINED, 0),
    ]
    for play_modes, flag in PLAY_MODE_FEATURE_FLAGS:
        dmr_device_mock.valid_play_modes = {play_modes}
        attrs = await get_attrs(hass, mock_entity_id)
        assert attrs[ha_const.ATTR_SUPPORTED_FEATURES] == expected_features | flag


async def test_attributes(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test attributes of a connected DlnaDmrEntity."""
    # Check attributes come directly from the device
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_VOLUME_LEVEL] is dmr_device_mock.volume_level
    assert attrs[mp.ATTR_MEDIA_VOLUME_MUTED] is dmr_device_mock.is_volume_muted
    assert attrs[mp.ATTR_MEDIA_DURATION] is dmr_device_mock.media_duration
    assert attrs[mp.ATTR_MEDIA_POSITION] is dmr_device_mock.media_position
    assert (
        attrs[mp.ATTR_MEDIA_POSITION_UPDATED_AT]
        is dmr_device_mock.media_position_updated_at
    )
    assert attrs[mp.ATTR_MEDIA_CONTENT_ID] is dmr_device_mock.current_track_uri
    assert attrs[mp.ATTR_MEDIA_ARTIST] is dmr_device_mock.media_artist
    assert attrs[mp.ATTR_MEDIA_ALBUM_NAME] is dmr_device_mock.media_album_name
    assert attrs[mp.ATTR_MEDIA_ALBUM_ARTIST] is dmr_device_mock.media_album_artist
    assert attrs[mp.ATTR_MEDIA_TRACK] is dmr_device_mock.media_track_number
    assert attrs[mp.ATTR_MEDIA_SERIES_TITLE] is dmr_device_mock.media_series_title
    assert attrs[mp.ATTR_MEDIA_SEASON] is dmr_device_mock.media_season_number
    assert attrs[mp.ATTR_MEDIA_EPISODE] is dmr_device_mock.media_episode_number
    assert attrs[mp.ATTR_MEDIA_CHANNEL] is dmr_device_mock.media_channel_name
    assert attrs[mp.ATTR_SOUND_MODE_LIST] is dmr_device_mock.preset_names

    # Entity picture is cached, won't correspond to remote image
    assert isinstance(attrs[ha_const.ATTR_ENTITY_PICTURE], str)

    # media_title depends on what is available
    assert attrs[mp.ATTR_MEDIA_TITLE] is dmr_device_mock.media_program_title
    dmr_device_mock.media_program_title = None
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_TITLE] is dmr_device_mock.media_title

    # media_content_type is mapped from UPnP class to MediaPlayer type
    dmr_device_mock.media_class = "object.item.audioItem.musicTrack"
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    dmr_device_mock.media_class = "object.item.videoItem.movie"
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_CONTENT_TYPE] == MediaType.MOVIE
    dmr_device_mock.media_class = "object.item.videoItem.videoBroadcast"
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_CONTENT_TYPE] == MediaType.TVSHOW

    # media_season & media_episode have a special case
    dmr_device_mock.media_season_number = "0"
    dmr_device_mock.media_episode_number = "123"
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_SEASON] == "1"
    assert attrs[mp.ATTR_MEDIA_EPISODE] == "23"
    dmr_device_mock.media_season_number = "0"
    dmr_device_mock.media_episode_number = "S1E23"  # Unexpected and not parsed
    attrs = await get_attrs(hass, mock_entity_id)
    assert attrs[mp.ATTR_MEDIA_SEASON] == "0"
    assert attrs[mp.ATTR_MEDIA_EPISODE] == "S1E23"

    # shuffle and repeat is based on device's play mode
    for play_mode, shuffle, repeat in (
        (PlayMode.NORMAL, False, RepeatMode.OFF),
        (PlayMode.SHUFFLE, True, RepeatMode.OFF),
        (PlayMode.REPEAT_ONE, False, RepeatMode.ONE),
        (PlayMode.REPEAT_ALL, False, RepeatMode.ALL),
        (PlayMode.RANDOM, True, RepeatMode.ALL),
        (PlayMode.DIRECT_1, False, RepeatMode.OFF),
        (PlayMode.INTRO, False, RepeatMode.OFF),
    ):
        dmr_device_mock.play_mode = play_mode
        attrs = await get_attrs(hass, mock_entity_id)
        assert attrs[mp.ATTR_MEDIA_SHUFFLE] is shuffle
        assert attrs[mp.ATTR_MEDIA_REPEAT] == repeat
    for bad_play_mode in (None, PlayMode.VENDOR_DEFINED):
        dmr_device_mock.play_mode = bad_play_mode
        attrs = await get_attrs(hass, mock_entity_id)
        assert mp.ATTR_MEDIA_SHUFFLE not in attrs
        assert mp.ATTR_MEDIA_REPEAT not in attrs


async def test_services(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test service calls of a connected DlnaDmrEntity."""
    # Check interface methods interact directly with the device
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
        blocking=True,
    )
    dmr_device_mock.async_set_volume_level.assert_awaited_once_with(0.80)
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    dmr_device_mock.async_mute_volume.assert_awaited_once_with(True)
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_pause.assert_awaited_once_with()
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_pause.assert_awaited_once_with()
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_stop.assert_awaited_once_with()
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_next.assert_awaited_once_with()
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_previous.assert_awaited_once_with()
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_SEEK_POSITION: 33},
        blocking=True,
    )
    dmr_device_mock.async_seek_rel_time.assert_awaited_once_with(timedelta(seconds=33))
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_SOUND_MODE: "Default"},
        blocking=True,
    )
    dmr_device_mock.async_select_preset.assert_awaited_once_with("Default")


async def test_play_media_stopped(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media, starting from stopped and the device can stop."""
    # play_media performs a few calls to the device for setup and play
    dmr_device_mock.can_stop = True
    dmr_device_mock.transport_state = TransportState.STOPPED
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            mp.ATTR_MEDIA_CONTENT_ID: (
                "http://198.51.100.20:8200/MediaItems/17621.mp3"
            ),
            mp.ATTR_MEDIA_ENQUEUE: False,
        },
        blocking=True,
    )

    dmr_device_mock.construct_play_media_metadata.assert_awaited_once_with(
        media_url="http://198.51.100.20:8200/MediaItems/17621.mp3",
        media_title="Home Assistant",
        override_upnp_class="object.item.audioItem.musicTrack",
        meta_data={},
    )
    dmr_device_mock.async_stop.assert_awaited_once_with()
    dmr_device_mock.async_set_transport_uri.assert_awaited_once_with(
        "http://198.51.100.20:8200/MediaItems/17621.mp3", "Home Assistant", ANY
    )
    dmr_device_mock.async_wait_for_can_play.assert_awaited_once_with()
    dmr_device_mock.async_play.assert_awaited_once_with()


async def test_play_media_playing(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media, device is already playing and can't stop."""
    dmr_device_mock.can_stop = False
    dmr_device_mock.transport_state = TransportState.PLAYING
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            mp.ATTR_MEDIA_CONTENT_ID: (
                "http://198.51.100.20:8200/MediaItems/17621.mp3"
            ),
            mp.ATTR_MEDIA_ENQUEUE: False,
        },
        blocking=True,
    )

    dmr_device_mock.construct_play_media_metadata.assert_awaited_once_with(
        media_url="http://198.51.100.20:8200/MediaItems/17621.mp3",
        media_title="Home Assistant",
        override_upnp_class="object.item.audioItem.musicTrack",
        meta_data={},
    )
    dmr_device_mock.async_stop.assert_not_awaited()
    dmr_device_mock.async_set_transport_uri.assert_awaited_once_with(
        "http://198.51.100.20:8200/MediaItems/17621.mp3", "Home Assistant", ANY
    )
    dmr_device_mock.async_wait_for_can_play.assert_not_awaited()
    dmr_device_mock.async_play.assert_not_awaited()


async def test_play_media_no_autoplay(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media with autoplay=False."""
    # play_media performs a few calls to the device for setup and play
    dmr_device_mock.can_stop = True
    dmr_device_mock.transport_state = TransportState.STOPPED
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            mp.ATTR_MEDIA_CONTENT_ID: (
                "http://198.51.100.20:8200/MediaItems/17621.mp3"
            ),
            mp.ATTR_MEDIA_ENQUEUE: False,
            mp.ATTR_MEDIA_EXTRA: {"autoplay": False},
        },
        blocking=True,
    )

    dmr_device_mock.construct_play_media_metadata.assert_awaited_once_with(
        media_url="http://198.51.100.20:8200/MediaItems/17621.mp3",
        media_title="Home Assistant",
        override_upnp_class="object.item.audioItem.musicTrack",
        meta_data={},
    )
    dmr_device_mock.async_stop.assert_awaited_once_with()
    dmr_device_mock.async_set_transport_uri.assert_awaited_once_with(
        "http://198.51.100.20:8200/MediaItems/17621.mp3", "Home Assistant", ANY
    )
    dmr_device_mock.async_wait_for_can_play.assert_not_awaited()
    dmr_device_mock.async_play.assert_not_awaited()


async def test_play_media_metadata(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media constructs useful metadata from user params."""
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            mp.ATTR_MEDIA_CONTENT_ID: (
                "http://198.51.100.20:8200/MediaItems/17621.mp3"
            ),
            mp.ATTR_MEDIA_ENQUEUE: False,
            mp.ATTR_MEDIA_EXTRA: {
                "title": "Mock song",
                "thumb": "http://198.51.100.20:8200/MediaItems/17621.jpg",
                "metadata": {"artist": "Mock artist", "album": "Mock album"},
            },
        },
        blocking=True,
    )

    dmr_device_mock.construct_play_media_metadata.assert_awaited_once_with(
        media_url="http://198.51.100.20:8200/MediaItems/17621.mp3",
        media_title="Mock song",
        override_upnp_class="object.item.audioItem.musicTrack",
        meta_data={
            "artist": "Mock artist",
            "album": "Mock album",
            "album_art_uri": "http://198.51.100.20:8200/MediaItems/17621.jpg",
        },
    )

    # Check again for a different media type
    dmr_device_mock.construct_play_media_metadata.reset_mock()
    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.TVSHOW,
            mp.ATTR_MEDIA_CONTENT_ID: ("http://198.51.100.20:8200/MediaItems/123.mkv"),
            mp.ATTR_MEDIA_ENQUEUE: False,
            mp.ATTR_MEDIA_EXTRA: {
                "title": "Mock show",
                "metadata": {"season": 1, "episode": 12},
            },
        },
        blocking=True,
    )

    dmr_device_mock.construct_play_media_metadata.assert_awaited_once_with(
        media_url="http://198.51.100.20:8200/MediaItems/123.mkv",
        media_title="Mock show",
        override_upnp_class="object.item.videoItem.videoBroadcast",
        meta_data={"episodeSeason": 1, "episodeNumber": 12},
    )


async def test_play_media_local_source(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media with a media_id from a local media_source."""
    # Based on roku's test_services_play_media_local_source and cast's
    # test_entity_browse_media
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        mp.DOMAIN,
        mp.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_CONTENT_TYPE: "video/mp4",
            mp.ATTR_MEDIA_CONTENT_ID: (
                "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
            ),
        },
        blocking=True,
    )

    assert dmr_device_mock.construct_play_media_metadata.await_count == 1
    assert (
        "/media/local/Epic%20Sax%20Guy%2010%20Hours.mp4?authSig="
        in dmr_device_mock.construct_play_media_metadata.call_args.kwargs["media_url"]
    )
    assert dmr_device_mock.async_set_transport_uri.await_count == 1
    assert dmr_device_mock.async_play.await_count == 1
    call_args = dmr_device_mock.async_set_transport_uri.call_args.args
    assert "/media/local/Epic%20Sax%20Guy%2010%20Hours.mp4?authSig=" in call_args[0]


async def test_play_media_didl_metadata(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test play_media passes available DIDL-Lite metadata to the DMR."""

    @dataclass
    class DidlPlayMedia(PlayMedia):
        """Playable media with DIDL metadata."""

        didl_metadata: didl_lite.DidlObject

    didl_metadata = didl_lite.VideoItem(
        id="120$22$33",
        restricted="false",
        title="Epic Sax Guy 10 Hours",
        res=[
            didl_lite.Resource(uri="unused-URI", protocol_info="http-get:*:video/mp4:")
        ],
    )

    play_media = DidlPlayMedia(
        url="/media/local/Epic Sax Guy 10 Hours.mp4",
        mime_type="video/mp4",
        didl_metadata=didl_metadata,
    )

    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=play_media,
    ):
        await hass.services.async_call(
            mp.DOMAIN,
            mp.SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: mock_entity_id,
                mp.ATTR_MEDIA_CONTENT_TYPE: "video/mp4",
                mp.ATTR_MEDIA_CONTENT_ID: (
                    "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
                ),
            },
            blocking=True,
        )

    assert dmr_device_mock.construct_play_media_metadata.await_count == 0
    assert dmr_device_mock.async_set_transport_uri.await_count == 1
    assert dmr_device_mock.async_play.await_count == 1
    call_args = dmr_device_mock.async_set_transport_uri.call_args.args
    assert "/media/local/Epic%20Sax%20Guy%2010%20Hours.mp4?authSig=" in call_args[0]
    assert call_args[1] == "Epic Sax Guy 10 Hours"
    assert call_args[2] == didl_lite.to_xml_string(didl_metadata).decode()


async def test_shuffle_repeat_modes(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test setting repeat and shuffle modes."""
    # Test shuffle with all variations of existing play mode
    dmr_device_mock.valid_play_modes = {mode.value for mode in PlayMode}
    for init_mode, shuffle_set, expect_mode in (
        (PlayMode.NORMAL, False, PlayMode.NORMAL),
        (PlayMode.SHUFFLE, False, PlayMode.NORMAL),
        (PlayMode.REPEAT_ONE, False, PlayMode.REPEAT_ONE),
        (PlayMode.REPEAT_ALL, False, PlayMode.REPEAT_ALL),
        (PlayMode.RANDOM, False, PlayMode.REPEAT_ALL),
        (PlayMode.NORMAL, True, PlayMode.SHUFFLE),
        (PlayMode.SHUFFLE, True, PlayMode.SHUFFLE),
        (PlayMode.REPEAT_ONE, True, PlayMode.RANDOM),
        (PlayMode.REPEAT_ALL, True, PlayMode.RANDOM),
        (PlayMode.RANDOM, True, PlayMode.RANDOM),
    ):
        dmr_device_mock.play_mode = init_mode
        await hass.services.async_call(
            mp.DOMAIN,
            ha_const.SERVICE_SHUFFLE_SET,
            {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_SHUFFLE: shuffle_set},
            blocking=True,
        )
        dmr_device_mock.async_set_play_mode.assert_awaited_with(expect_mode)

    # Test repeat with all variations of existing play mode
    for init_mode, repeat_set, expect_mode in (
        (PlayMode.NORMAL, RepeatMode.OFF, PlayMode.NORMAL),
        (PlayMode.SHUFFLE, RepeatMode.OFF, PlayMode.SHUFFLE),
        (PlayMode.REPEAT_ONE, RepeatMode.OFF, PlayMode.NORMAL),
        (PlayMode.REPEAT_ALL, RepeatMode.OFF, PlayMode.NORMAL),
        (PlayMode.RANDOM, RepeatMode.OFF, PlayMode.SHUFFLE),
        (PlayMode.NORMAL, RepeatMode.ONE, PlayMode.REPEAT_ONE),
        (PlayMode.SHUFFLE, RepeatMode.ONE, PlayMode.REPEAT_ONE),
        (PlayMode.REPEAT_ONE, RepeatMode.ONE, PlayMode.REPEAT_ONE),
        (PlayMode.REPEAT_ALL, RepeatMode.ONE, PlayMode.REPEAT_ONE),
        (PlayMode.RANDOM, RepeatMode.ONE, PlayMode.REPEAT_ONE),
        (PlayMode.NORMAL, RepeatMode.ALL, PlayMode.REPEAT_ALL),
        (PlayMode.SHUFFLE, RepeatMode.ALL, PlayMode.RANDOM),
        (PlayMode.REPEAT_ONE, RepeatMode.ALL, PlayMode.REPEAT_ALL),
        (PlayMode.REPEAT_ALL, RepeatMode.ALL, PlayMode.REPEAT_ALL),
        (PlayMode.RANDOM, RepeatMode.ALL, PlayMode.RANDOM),
    ):
        dmr_device_mock.play_mode = init_mode
        await hass.services.async_call(
            mp.DOMAIN,
            ha_const.SERVICE_REPEAT_SET,
            {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_REPEAT: repeat_set},
            blocking=True,
        )
        dmr_device_mock.async_set_play_mode.assert_awaited_with(expect_mode)

    # Test shuffle when the device doesn't support the desired play mode.
    # Trying to go from RANDOM -> REPEAT_MODE_ALL, but nothing in the list is supported.
    dmr_device_mock.async_set_play_mode.reset_mock()
    dmr_device_mock.play_mode = PlayMode.RANDOM
    dmr_device_mock.valid_play_modes = {PlayMode.SHUFFLE, PlayMode.RANDOM}
    await get_attrs(hass, mock_entity_id)
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_SHUFFLE: False},
        blocking=True,
    )
    dmr_device_mock.async_set_play_mode.assert_not_awaited()

    # Test repeat when the device doesn't support the desired play mode.
    # Trying to go from RANDOM -> SHUFFLE, but nothing in the list is supported.
    dmr_device_mock.async_set_play_mode.reset_mock()
    dmr_device_mock.play_mode = PlayMode.RANDOM
    dmr_device_mock.valid_play_modes = {PlayMode.REPEAT_ONE, PlayMode.REPEAT_ALL}
    await get_attrs(hass, mock_entity_id)
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp.ATTR_MEDIA_REPEAT: RepeatMode.OFF,
        },
        blocking=True,
    )
    dmr_device_mock.async_set_play_mode.assert_not_awaited()


async def test_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test the async_browse_media method."""
    # Based on cast's test_entity_browse_media
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})
    await hass.async_block_till_done()

    # DMR can play all media types
    dmr_device_mock.sink_protocol_info = ["*"]

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child_video = {
        "title": "Epic Sax Guy 10 Hours.mp4",
        "media_class": "video",
        "media_content_type": "video/mp4",
        "media_content_id": (
            "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
        ),
        "can_play": True,
        "can_expand": False,
        "can_search": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_video in response["result"]["children"]

    expected_child_audio = {
        "title": "test.mp3",
        "media_class": "music",
        "media_content_type": "audio/mpeg",
        "media_content_id": "media-source://media_source/local/test.mp3",
        "can_play": True,
        "can_expand": False,
        "can_search": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_audio in response["result"]["children"]

    # Device can only play MIME type audio/mpeg and audio/vorbis
    dmr_device_mock.sink_protocol_info = [
        "http-get:*:audio/mpeg:*",
        "http-get:*:audio/vorbis:*",
    ]
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    # Video file should not be shown
    assert expected_child_video not in response["result"]["children"]
    # Audio file should appear
    assert expected_child_audio in response["result"]["children"]

    # Device specifies extra parameters in MIME type, uses non-standard "x-"
    # prefix, and capitalizes things, all of which should be ignored
    dmr_device_mock.sink_protocol_info = [
        "http-get:*:audio/X-MPEG;codecs=mp3:*",
    ]
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    # Video file should not be shown
    assert expected_child_video not in response["result"]["children"]
    # Audio file should appear
    assert expected_child_audio in response["result"]["children"]

    # Device does not specify what it can play
    dmr_device_mock.sink_protocol_info = []
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    # All files should be returned
    assert expected_child_video in response["result"]["children"]
    assert expected_child_audio in response["result"]["children"]


async def test_browse_media_unfiltered(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test the async_browse_media method with filtering turned off and on."""
    # Based on cast's test_entity_browse_media
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})
    await hass.async_block_till_done()

    expected_child_video = {
        "title": "Epic Sax Guy 10 Hours.mp4",
        "media_class": "video",
        "media_content_type": "video/mp4",
        "media_content_id": (
            "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
        ),
        "can_play": True,
        "can_expand": False,
        "can_search": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    expected_child_audio = {
        "title": "test.mp3",
        "media_class": "music",
        "media_content_type": "audio/mpeg",
        "media_content_id": "media-source://media_source/local/test.mp3",
        "can_play": True,
        "can_expand": False,
        "can_search": False,
        "thumbnail": None,
        "children_media_class": None,
    }

    # Device can only play MIME type audio/mpeg and audio/vorbis
    dmr_device_mock.sink_protocol_info = [
        "http-get:*:audio/mpeg:*",
        "http-get:*:audio/vorbis:*",
    ]

    # Filtering turned on by default
    assert CONF_BROWSE_UNFILTERED not in config_entry_mock.options

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    # Video file should not be shown
    assert expected_child_video not in response["result"]["children"]
    # Audio file should appear
    assert expected_child_audio in response["result"]["children"]

    # Filtering turned off via config entry
    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_BROWSE_UNFILTERED: True,
        },
    )
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": mock_entity_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    # All files should be returned
    assert expected_child_video in response["result"]["children"]
    assert expected_child_audio in response["result"]["children"]


async def test_playback_update_state(
    hass: HomeAssistant, dmr_device_mock: Mock, mock_entity_id: str
) -> None:
    """Test starting or pausing playback causes the state to be refreshed.

    This is necessary for responsive updates of the current track position and
    total track time.
    """
    on_event = dmr_device_mock.on_event
    mock_service = Mock(UpnpService)
    mock_service.service_id = "urn:upnp-org:serviceId:AVTransport"
    mock_state_variable = Mock(UpnpStateVariable)
    mock_state_variable.name = "TransportState"

    # Event update that device has started playing, device should get polled
    mock_state_variable.value = TransportState.PLAYING
    on_event(mock_service, [mock_state_variable])
    await hass.async_block_till_done()
    dmr_device_mock.async_update.assert_awaited_once_with(do_ping=False)

    # Event update that device has paused playing, device should get polled
    dmr_device_mock.async_update.reset_mock()
    mock_state_variable.value = TransportState.PAUSED_PLAYBACK
    on_event(mock_service, [mock_state_variable])
    await hass.async_block_till_done()
    dmr_device_mock.async_update.assert_awaited_once_with(do_ping=False)

    # Different service shouldn't do anything
    dmr_device_mock.async_update.reset_mock()
    mock_service.service_id = "urn:upnp-org:serviceId:RenderingControl"
    on_event(mock_service, [mock_state_variable])
    await hass.async_block_till_done()
    dmr_device_mock.async_update.assert_not_awaited()


@pytest.mark.parametrize(
    "core_state",
    [CoreState.not_running, CoreState.running],
)
async def test_unavailable_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    core_state: CoreState,
) -> None:
    """Test a DlnaDmrEntity with out a connected DmrDevice."""
    # Cause connection attempts to fail
    hass.set_state(core_state)
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)

    with patch(
        "homeassistant.components.dlna_dmr.media_player.DmrDevice", autospec=True
    ) as dmr_device_constructor_mock:
        mock_entity_id = await setup_mock_component(hass, config_entry_mock)
        mock_state = hass.states.get(mock_entity_id)
        assert mock_state is not None

        # Check device is not created
        dmr_device_constructor_mock.assert_not_called()

    # Check attempt was made to create a device from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    # Check event notifiers are not acquired
    domain_data_mock.async_get_event_notifier.assert_not_called()
    # Check SSDP notifications are registered
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"USN": MOCK_DEVICE_USN}
    )
    ssdp_scanner_mock.async_register_callback.assert_any_call(
        ANY, {"_udn": MOCK_DEVICE_UDN, "NTS": "ssdp:byebye"}
    )
    # Quick check of the state to verify the entity has no connected DmrDevice
    assert mock_state.state == ha_const.STATE_UNAVAILABLE
    # Check the name matches that supplied
    assert mock_state.name == MOCK_DEVICE_NAME

    # Check that an update does not attempt to contact the device because
    # poll_availability is False
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await async_update_entity(hass, mock_entity_id)
    domain_data_mock.upnp_factory.async_create_device.assert_not_called()

    # Now set poll_availability = True and expect construction attempt
    hass.config_entries.async_update_entry(
        config_entry_mock, options={CONF_POLL_AVAILABILITY: True}
    )
    await hass.async_block_till_done()
    await async_update_entity(hass, mock_entity_id)
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    # Check attributes are unavailable
    attrs = mock_state.attributes
    for attr in mp.ATTR_TO_PROPERTY:
        assert attr not in attrs

    assert attrs[ha_const.ATTR_FRIENDLY_NAME] == MOCK_DEVICE_NAME
    assert attrs[ha_const.ATTR_SUPPORTED_FEATURES] == 0
    assert mp.ATTR_SOUND_MODE_LIST not in attrs

    # Check service calls do nothing
    SERVICES: list[tuple[str, dict]] = [
        (ha_const.SERVICE_VOLUME_SET, {mp.ATTR_MEDIA_VOLUME_LEVEL: 0.80}),
        (ha_const.SERVICE_VOLUME_MUTE, {mp.ATTR_MEDIA_VOLUME_MUTED: True}),
        (ha_const.SERVICE_MEDIA_PAUSE, {}),
        (ha_const.SERVICE_MEDIA_PLAY, {}),
        (ha_const.SERVICE_MEDIA_STOP, {}),
        (ha_const.SERVICE_MEDIA_NEXT_TRACK, {}),
        (ha_const.SERVICE_MEDIA_PREVIOUS_TRACK, {}),
        (ha_const.SERVICE_MEDIA_SEEK, {mp.ATTR_MEDIA_SEEK_POSITION: 33}),
        (
            mp.SERVICE_PLAY_MEDIA,
            {
                mp.ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                mp.ATTR_MEDIA_CONTENT_ID: (
                    "http://198.51.100.20:8200/MediaItems/17621.mp3"
                ),
                mp.ATTR_MEDIA_ENQUEUE: False,
            },
        ),
        (mp.SERVICE_SELECT_SOUND_MODE, {mp.ATTR_SOUND_MODE: "Default"}),
        (ha_const.SERVICE_SHUFFLE_SET, {mp.ATTR_MEDIA_SHUFFLE: True}),
        (ha_const.SERVICE_REPEAT_SET, {mp.ATTR_MEDIA_REPEAT: "all"}),
    ]
    for service, data in SERVICES:
        await hass.services.async_call(
            mp.DOMAIN,
            service,
            {ATTR_ENTITY_ID: mock_entity_id, **data},
            blocking=True,
        )

    # Check hass device information has not been filled in yet
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert device.name is None
    assert device.manufacturer is None

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Check event notifiers are not released
    domain_data_mock.async_release_event_notifier.assert_not_called()

    # Entity should be removed by the cleanup
    assert hass.states.get(mock_entity_id) is None


@pytest.mark.parametrize(
    "core_state",
    [CoreState.not_running, CoreState.running],
)
async def test_become_available(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    core_state: CoreState,
) -> None:
    """Test a device becoming available after the entity is constructed."""
    # Cause connection attempts to fail before adding entity
    hass.set_state(core_state)
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check hass device information has not been filled in yet
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None

    # Mock device is now available.
    domain_data_mock.upnp_factory.async_create_device.side_effect = None
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Send an SSDP notification from the now alive device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        NEW_DEVICE_LOCATION
    )
    # Check event notifiers are acquired
    domain_data_mock.async_get_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None), hass
    )
    # Check UPnP services are subscribed
    dmr_device_mock.async_subscribe_services.assert_awaited_once_with(
        auto_resubscribe=True
    )
    assert dmr_device_mock.on_event is not None
    # Quick check of the state to verify the entity has a connected DmrDevice
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE
    # Check hass device information is now filled in
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert device.manufacturer == "device_manufacturer"
    assert device.model == "device_model_name"
    assert device.name == "device_name"

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Confirm the entity has disconnected from the device
    domain_data_mock.async_release_event_notifier.assert_awaited_once()
    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()
    assert dmr_device_mock.on_event is None
    # Entity should be removed by the cleanup
    assert hass.states.get(mock_entity_id) is None


@pytest.mark.parametrize(
    "core_state",
    [CoreState.not_running, CoreState.running],
)
async def test_alive_but_gone(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
    core_state: CoreState,
) -> None:
    """Test a device sending an SSDP alive announcement, but not being connectable."""
    hass.set_state(core_state)
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    # Send an SSDP notification from the still missing device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # There should be a connection attempt to the device
    domain_data_mock.upnp_factory.async_create_device.assert_awaited()

    # Device should still be unavailable
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Send the same SSDP notification, expecting no extra connection attempts
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()
    domain_data_mock.upnp_factory.async_create_device.assert_not_called()
    domain_data_mock.upnp_factory.async_create_device.assert_not_awaited()
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Send an SSDP notification with a new BOOTID, indicating the device has rebooted
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Rebooted device (seen via BOOTID) should mean a new connection attempt
    domain_data_mock.upnp_factory.async_create_device.assert_awaited()
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Send byebye message to indicate device is going away. Next alive message
    # should result in a reconnect attempt even with same BOOTID.
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Rebooted device (seen via byebye/alive) should mean a new connection attempt
    domain_data_mock.upnp_factory.async_create_device.assert_awaited()
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_multiple_ssdp_alive(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
) -> None:
    """Test multiple SSDP alive notifications is ok, only connects to device once."""
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Contacting the device takes long enough that 2 simultaneous attempts could be made
    async def create_device_delayed(_location):
        """Delay before continuing with async_create_device.

        This gives a chance for parallel calls to `_device_connect` to occur.
        """
        await asyncio.sleep(0.1)
        return DEFAULT

    domain_data_mock.upnp_factory.async_create_device.side_effect = (
        create_device_delayed
    )

    # Send two SSDP notifications with the new device URL
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device is contacted exactly once
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        NEW_DEVICE_LOCATION
    )

    # Device should be available
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE


async def test_ssdp_byebye(
    hass: HomeAssistant,
    ssdp_scanner_mock: Mock,
    mock_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test device is disconnected when byebye is received."""
    # First byebye will cause a disconnect
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={"NTS": "ssdp:byebye"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )

    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()

    # Device should be gone
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Second byebye will do nothing
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={"NTS": "ssdp:byebye"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )

    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()


async def test_ssdp_update_seen_bootid(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test device does not reconnect when it gets ssdp:update with next bootid."""
    # Start with a disconnected device
    entity_id = mock_disconnected_entity_id
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # "Reconnect" the device
    domain_data_mock.upnp_factory.async_create_device.side_effect = None

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Send SSDP update with next boot ID
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "1",
                ssdp.ATTR_SSDP_NEXTBOOTID: "2",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Device was not reconnected, even with a new boot ID
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1

    # Send SSDP update with same next boot ID, again
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "1",
                ssdp.ATTR_SSDP_NEXTBOOTID: "2",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Nothing should change
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1

    # Send SSDP update with bad next boot ID
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "2",
                ssdp.ATTR_SSDP_NEXTBOOTID: "7c848375-a106-4bd1-ac3c-8e50427c8e4f",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Nothing should change
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1

    # Send a new SSDP alive with the new boot ID, device should not reconnect
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1


async def test_ssdp_update_missed_bootid(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test device disconnects when it gets ssdp:update bootid it wasn't expecting."""
    # Start with a disconnected device
    entity_id = mock_disconnected_entity_id
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # "Reconnect" the device
    domain_data_mock.upnp_factory.async_create_device.side_effect = None

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Send SSDP update with skipped boot ID (not previously seen)
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={
                "NTS": "ssdp:update",
                ssdp.ATTR_SSDP_BOOTID: "2",
                ssdp.ATTR_SSDP_NEXTBOOTID: "3",
            },
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.UPDATE,
    )
    await hass.async_block_till_done()

    # Device should not reconnect yet
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1

    # Send a new SSDP alive with the new boot ID, device should reconnect
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "3"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_unsubscribe_services.await_count == 1
    assert dmr_device_mock.async_subscribe_services.await_count == 2


async def test_ssdp_bootid(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test an alive with a new BOOTID.UPNP.ORG header causes a reconnect."""
    # Start with a disconnected device
    entity_id = mock_disconnected_entity_id
    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # "Reconnect" the device
    domain_data_mock.upnp_factory.async_create_device.side_effect = None

    # Send SSDP alive with boot ID
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 1
    assert dmr_device_mock.async_unsubscribe_services.call_count == 0

    # Send SSDP alive with same boot ID, nothing should happen
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "1"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 1
    assert dmr_device_mock.async_unsubscribe_services.call_count == 0

    # Send a new SSDP alive with an incremented boot ID, device should be dis/reconnected
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=MOCK_DEVICE_LOCATION,
            ssdp_headers={ssdp.ATTR_SSDP_BOOTID: "2"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 2
    assert dmr_device_mock.async_unsubscribe_services.call_count == 1


async def test_become_unavailable(
    hass: HomeAssistant,
    mock_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test a device becoming unavailable."""
    # Check async_update currently works
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_called_with(do_ping=False)

    # Now break the network connection and try to contact the device
    dmr_device_mock.async_set_volume_level.side_effect = UpnpConnectionError
    dmr_device_mock.async_update.reset_mock()

    # Interface service calls should flag that the device is unavailable, but
    # not disconnect it immediately
    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
        blocking=True,
    )

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    # With a working connection, the state should be restored
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_any_call(do_ping=True)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    # Break the service again, and the connection too. An update will cause the
    # device to be disconnected
    dmr_device_mock.async_update.reset_mock()
    dmr_device_mock.async_update.side_effect = UpnpConnectionError

    await hass.services.async_call(
        mp.DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
        blocking=True,
    )
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_called_with(do_ping=True)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_poll_availability(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test device becomes available and noticed via poll_availability."""
    # Start with a disconnected device and poll_availability=True
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_POLL_AVAILABILITY: True,
        },
    )
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check that an update will poll the device for availability
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()

    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # "Reconnect" the device
    domain_data_mock.upnp_factory.async_create_device.side_effect = None

    # Check that an update will notice the device and connect to it
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await async_update_entity(hass, mock_entity_id)
    await hass.async_block_till_done()

    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    # Clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


async def test_disappearing_device(
    hass: HomeAssistant,
    mock_disconnected_entity_id: str,
) -> None:
    """Test attribute update or service call as device disappears.

    Normally HA will check if the entity is available before updating attributes
    or calling a service, but it's possible for the device to go offline in
    between the check and the method call. Here we test by accessing the entity
    directly to skip the availability check.
    """
    # Retrieve entity directly.
    entity: DlnaDmrEntity = hass.data[mp.DOMAIN].get_entity(mock_disconnected_entity_id)

    # Test attribute access
    for attr in mp.ATTR_TO_PROPERTY:
        value = getattr(entity, attr)
        assert value is None

    # media_image_url is normally hidden by entity_picture, but we want a direct check
    assert entity.media_image_url is None

    # Check attributes that are normally pre-checked
    assert entity.sound_mode_list is None

    # Test service calls
    await entity.async_set_volume_level(0.1)
    await entity.async_mute_volume(True)
    await entity.async_media_pause()
    await entity.async_media_play()
    await entity.async_media_stop()
    await entity.async_media_seek(22.0)
    await entity.async_play_media("", "")
    await entity.async_media_previous_track()
    await entity.async_media_next_track()
    await entity.async_set_shuffle(True)
    await entity.async_set_repeat(RepeatMode.ALL)
    await entity.async_select_sound_mode("Default")


async def test_resubscribe_failure(
    hass: HomeAssistant,
    mock_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test failure to resubscribe to events notifications causes an update ping."""
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_called_with(do_ping=False)
    dmr_device_mock.async_update.reset_mock()

    on_event = dmr_device_mock.on_event
    mock_service = Mock(UpnpService)
    on_event(mock_service, [])
    await hass.async_block_till_done()

    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_called_with(do_ping=True)


async def test_config_update_listen_port(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test DlnaDmrEntity gets updated by ConfigEntry's CONF_LISTEN_PORT."""
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_LISTEN_PORT: 1234,
        },
    )
    await hass.async_block_till_done()

    # A new event listener with the changed port will be used
    domain_data_mock.async_release_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None)
    )
    domain_data_mock.async_get_event_notifier.assert_awaited_with(
        EventListenAddr(LOCAL_IP, 1234, None), hass
    )

    # Device will be reconnected
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    assert dmr_device_mock.async_unsubscribe_services.await_count == 1
    assert dmr_device_mock.async_subscribe_services.await_count == 2

    # Check that its still connected
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE


async def test_config_update_connect_failure(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    mock_entity_id: str,
) -> None:
    """Test DlnaDmrEntity gracefully handles connect failure after config change."""
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_LISTEN_PORT: 1234,
        },
    )
    await hass.async_block_till_done()

    # Old event listener was released, new event listener was not created
    domain_data_mock.async_release_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None)
    )
    domain_data_mock.async_get_event_notifier.assert_awaited_once()

    # There was an attempt to connect to the device
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    # Check that its no longer connected
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_config_update_callback_url(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test DlnaDmrEntity gets updated by ConfigEntry's CONF_CALLBACK_URL_OVERRIDE."""
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_CALLBACK_URL_OVERRIDE: "http://www.example.net/notify",
        },
    )
    await hass.async_block_till_done()

    # A new event listener with the changed callback URL will be used
    domain_data_mock.async_release_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None)
    )
    domain_data_mock.async_get_event_notifier.assert_awaited_with(
        EventListenAddr(LOCAL_IP, 0, "http://www.example.net/notify"), hass
    )

    # Device will be reconnected
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    assert dmr_device_mock.async_unsubscribe_services.await_count == 1
    assert dmr_device_mock.async_subscribe_services.await_count == 2

    # Check that its still connected
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE


async def test_config_update_poll_availability(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test DlnaDmrEntity gets updated by ConfigEntry's CONF_POLL_AVAILABILITY."""
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Updates of the device will not ping it yet
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_awaited_with(do_ping=False)

    hass.config_entries.async_update_entry(
        config_entry_mock,
        options={
            CONF_POLL_AVAILABILITY: True,
        },
    )
    await hass.async_block_till_done()

    # Event listeners will not change
    domain_data_mock.async_release_event_notifier.assert_not_awaited()
    domain_data_mock.async_get_event_notifier.assert_awaited_once()

    # Device will not be reconnected
    domain_data_mock.upnp_factory.async_create_device.assert_not_awaited()
    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1

    # Updates of the device will now ping it
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_awaited_with(do_ping=True)

    # Check that its still connected
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE


async def test_config_update_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain_data_mock: Mock,
    config_entry_mock_no_mac: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
) -> None:
    """Test discovering the MAC address post-setup will update the device registry."""
    config_entry_mock_no_mac.add_to_hass(hass)
    await setup_mock_component(hass, config_entry_mock_no_mac)

    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Check the device registry connections does not include the MAC address
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, MOCK_MAC_ADDRESS) not in device.connections

    # MAC address discovered and set by config flow
    hass.config_entries.async_update_entry(
        config_entry_mock_no_mac,
        data={
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_DEVICE_ID: MOCK_DEVICE_UDN,
            CONF_TYPE: MOCK_DEVICE_TYPE,
            CONF_MAC: MOCK_MAC_ADDRESS,
        },
    )
    await hass.async_block_till_done()

    # Device registry connections should now include the MAC address
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, MOCK_MAC_ADDRESS) in device.connections


@pytest.mark.parametrize(
    "core_state",
    [CoreState.not_running, CoreState.running],
)
async def test_connections_restored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
    core_state: CoreState,
) -> None:
    """Test previous connections restored."""
    # Cause connection attempts to fail before adding entity
    hass.set_state(core_state)
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check hass device information has not been filled in yet
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None

    # Mock device is now available.
    domain_data_mock.upnp_factory.async_create_device.side_effect = None
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Send an SSDP notification from the now alive device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_location=NEW_DEVICE_LOCATION,
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        NEW_DEVICE_LOCATION
    )
    # Check event notifiers are acquired
    domain_data_mock.async_get_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 0, None), hass
    )
    # Check UPnP services are subscribed
    dmr_device_mock.async_subscribe_services.assert_awaited_once_with(
        auto_resubscribe=True
    )
    assert dmr_device_mock.on_event is not None
    # Quick check of the state to verify the entity has a connected DmrDevice
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE
    # Check hass device information is now filled in
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    previous_connections = device.connections
    assert device.manufacturer == "device_manufacturer"
    assert device.model == "device_model_name"
    assert device.name == "device_name"

    # Reload the config entry
    assert await hass.config_entries.async_reload(config_entry_mock.entry_id)
    await async_update_entity(hass, mock_entity_id)

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Confirm the entity has disconnected from the device
    domain_data_mock.async_release_event_notifier.assert_awaited_once()
    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()

    # Check hass device information has not been filled in yet
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_UPNP, MOCK_DEVICE_UDN)},
        identifiers=set(),
    )
    assert device is not None
    assert device.connections == previous_connections

    # Verify the entity remains linked to the device
    entry = entity_registry.async_get(mock_entity_id)
    assert entry is not None
    assert entry.device_id == device.id

    # Verify the entity has an idle state
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == MediaPlayerState.IDLE

    # Unload config entry to clean up
    assert await hass.config_entries.async_unload(config_entry_mock.entry_id)


async def test_udn_upnp_connection_added_if_missing(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test missing upnp connection added.

    We did not always add the upnp connection to the device registry, so we need to
    check that it is added if missing as otherwise we might end up creating a new
    device entry.
    """
    config_entry_mock.add_to_hass(hass)

    # Cause connection attempts to fail before adding entity
    entry = entity_registry.async_get_or_create(
        mp.DOMAIN,
        DOMAIN,
        MOCK_DEVICE_UDN,
        config_entry=config_entry_mock,
    )
    mock_entity_id = entry.entity_id

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry_mock.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_MAC_ADDRESS)},
        identifiers=set(),
    )

    entity_registry.async_update_entity(mock_entity_id, device_id=device.id)

    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id) is True
    await hass.async_block_till_done()

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check hass device information has not been filled in yet
    device = device_registry.async_get(device.id)
    assert device is not None
    assert (dr.CONNECTION_UPNP, MOCK_DEVICE_UDN) in device.connections
