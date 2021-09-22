"""Tests for the DLNA DMR media_player module."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from datetime import timedelta
from types import MappingProxyType
from unittest.mock import ANY, DEFAULT, Mock, patch

from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
from async_upnp_client.profiles.dlna import TransportState
import pytest

from homeassistant import const as ha_const
from homeassistant.components import ssdp
from homeassistant.components.dlna_dmr import media_player
from homeassistant.components.dlna_dmr.const import (
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN as DLNA_DOMAIN,
)
from homeassistant.components.dlna_dmr.data import EventListenAddr
from homeassistant.components.media_player import ATTR_TO_PROPERTY, const as mp_const
from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dr
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get as async_get_er,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    LOCAL_IP,
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_UDN,
    MOCK_DEVICE_USN,
    NEW_DEVICE_LOCATION,
)

from tests.common import MockConfigEntry

# Auto-use the domain_data_mock fixture for every test in this module
pytestmark = pytest.mark.usefixtures("domain_data_mock")


async def setup_mock_component(hass: HomeAssistant, mock_entry: MockConfigEntry) -> str:
    """Set up a mock DlnaDmrEntity with the given configuration."""
    mock_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DLNA_DOMAIN, {}) is True
    await hass.async_block_till_done()

    entries = async_entries_for_config_entry(async_get_er(hass), mock_entry.entry_id)
    assert len(entries) == 1
    entity_id = entries[0].entity_id

    return entity_id


@pytest.fixture
async def mock_entity_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> AsyncIterable[str]:
    """Fixture to set up a mock DlnaDmrEntity in a connected state.

    Yields the entity ID. Cleans up the entity after the test is complete.
    """
    entity_id = await setup_mock_component(hass, config_entry_mock)

    yield entity_id

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


@pytest.fixture
async def mock_disconnected_entity_id(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> AsyncIterable[str]:
    """Fixture to set up a mock DlnaDmrEntity in a disconnected state.

    Yields the entity ID. Cleans up the entity after the test is complete.
    """
    # Cause the connection attempt to fail
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError

    entity_id = await setup_mock_component(hass, config_entry_mock)

    yield entity_id

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


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
    config_entry_mock.options = MappingProxyType({})
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    # Check event notifiers are aquired
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
    assert mock_state.state == media_player.STATE_IDLE
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
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_setup_entry_with_options(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test setting options leads to a DlnaDmrEntity with custom event_handler.

    Check that the device is constructed properly as part of the test.
    """
    config_entry_mock.options = MappingProxyType(
        {
            CONF_LISTEN_PORT: 2222,
            CONF_CALLBACK_URL_OVERRIDE: "http://192.88.99.10/events",
            CONF_POLL_AVAILABILITY: True,
        }
    )
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )
    # Check event notifiers are aquired with the configured port and callback URL
    domain_data_mock.async_get_event_notifier.assert_awaited_once_with(
        EventListenAddr(LOCAL_IP, 2222, "http://192.88.99.10/events"), hass
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
    assert mock_state.state == media_player.STATE_IDLE
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
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_event_subscribe_failure(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test _device_connect aborts when async_subscribe_services fails."""
    dmr_device_mock.async_subscribe_services.side_effect = UpnpError

    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
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


async def test_available_device(
    hass: HomeAssistant,
    dmr_device_mock: Mock,
    mock_entity_id: str,
) -> None:
    """Test a DlnaDmrEntity with a connected DmrDevice."""
    # Check hass device information is filled in
    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_device(identifiers={(DLNA_DOMAIN, MOCK_DEVICE_UDN)})
    assert device is not None
    # Device properties are set in dmr_device_mock before the entity gets constructed
    assert device.manufacturer == "device_manufacturer"
    assert device.model == "device_model_name"
    assert device.name == "device_name"

    # Check entity state gets updated when device changes state
    for (dev_state, ent_state) in [
        (None, ha_const.STATE_ON),
        (TransportState.STOPPED, ha_const.STATE_IDLE),
        (TransportState.PLAYING, ha_const.STATE_PLAYING),
        (TransportState.TRANSITIONING, ha_const.STATE_IDLE),
        (TransportState.PAUSED_PLAYBACK, ha_const.STATE_PAUSED),
        (TransportState.PAUSED_RECORDING, ha_const.STATE_PAUSED),
        (TransportState.RECORDING, ha_const.STATE_IDLE),
        (TransportState.NO_MEDIA_PRESENT, ha_const.STATE_IDLE),
        (TransportState.VENDOR_DEFINED, ha_const.STATE_UNKNOWN),
    ]:
        dmr_device_mock.device.available = True
        dmr_device_mock.transport_state = dev_state
        await async_update_entity(hass, mock_entity_id)
        entity_state = hass.states.get(mock_entity_id)
        assert entity_state is not None
        assert entity_state.state == ent_state

    dmr_device_mock.device.available = False
    dmr_device_mock.transport_state = TransportState.PLAYING
    await async_update_entity(hass, mock_entity_id)
    entity_state = hass.states.get(mock_entity_id)
    assert entity_state is not None
    assert entity_state.state == ha_const.STATE_UNAVAILABLE

    dmr_device_mock.device.available = True
    await async_update_entity(hass, mock_entity_id)

    # Check attributes come directly from the device
    entity_state = hass.states.get(mock_entity_id)
    assert entity_state is not None
    attrs = entity_state.attributes
    assert attrs is not None

    assert attrs[mp_const.ATTR_MEDIA_VOLUME_LEVEL] is dmr_device_mock.volume_level
    assert attrs[mp_const.ATTR_MEDIA_VOLUME_MUTED] is dmr_device_mock.is_volume_muted
    assert attrs[mp_const.ATTR_MEDIA_DURATION] is dmr_device_mock.media_duration
    assert attrs[mp_const.ATTR_MEDIA_POSITION] is dmr_device_mock.media_position
    assert (
        attrs[mp_const.ATTR_MEDIA_POSITION_UPDATED_AT]
        is dmr_device_mock.media_position_updated_at
    )
    assert attrs[mp_const.ATTR_MEDIA_TITLE] is dmr_device_mock.media_title
    # Entity picture is cached, won't correspond to remote image
    assert isinstance(attrs[ha_const.ATTR_ENTITY_PICTURE], str)

    # Check supported feature flags, one at a time
    FEATURE_FLAGS: list[tuple[str, int]] = [
        ("volume_level", mp_const.SUPPORT_VOLUME_SET),
        ("volume_mute", mp_const.SUPPORT_VOLUME_MUTE),
        ("play", mp_const.SUPPORT_PLAY),
        ("pause", mp_const.SUPPORT_PAUSE),
        ("stop", mp_const.SUPPORT_STOP),
        ("previous", mp_const.SUPPORT_PREVIOUS_TRACK),
        ("next", mp_const.SUPPORT_NEXT_TRACK),
        ("play_media", mp_const.SUPPORT_PLAY_MEDIA),
        ("seek_rel_time", mp_const.SUPPORT_SEEK),
    ]
    # Clear all feature properties
    for prop, _ in FEATURE_FLAGS:
        setattr(dmr_device_mock, f"has_{prop}", False)
    await async_update_entity(hass, mock_entity_id)
    entity_state = hass.states.get(mock_entity_id)
    assert entity_state is not None
    assert entity_state.attributes[ha_const.ATTR_SUPPORTED_FEATURES] == 0
    # Test the properties cumulatively
    expected_features = 0
    for prop, flag in FEATURE_FLAGS:
        setattr(dmr_device_mock, f"has_{prop}", True)
        expected_features |= flag
        await async_update_entity(hass, mock_entity_id)
        entity_state = hass.states.get(mock_entity_id)
        assert entity_state is not None
        assert (
            entity_state.attributes[ha_const.ATTR_SUPPORTED_FEATURES]
            == expected_features
        )

    # Check interface methods interact directly with the device
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp_const.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
        blocking=True,
    )
    dmr_device_mock.async_set_volume_level.assert_awaited_once_with(0.80)
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: mock_entity_id, mp_const.ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    dmr_device_mock.async_mute_volume.assert_awaited_once_with(True)
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_pause.assert_awaited_once_with()
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_pause.assert_awaited_once_with()
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_stop.assert_awaited_once_with()
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_next.assert_awaited_once_with()
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: mock_entity_id},
        blocking=True,
    )
    dmr_device_mock.async_previous.assert_awaited_once_with()
    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: mock_entity_id, mp_const.ATTR_MEDIA_SEEK_POSITION: 33},
        blocking=True,
    )
    dmr_device_mock.async_seek_rel_time.assert_awaited_once_with(timedelta(seconds=33))

    # play_media performs a few calls to the device for setup and play
    # Start from stopped, and device can stop too
    dmr_device_mock.can_stop = True
    dmr_device_mock.transport_state = TransportState.STOPPED
    dmr_device_mock.async_stop.reset_mock()
    dmr_device_mock.async_set_transport_uri.reset_mock()
    dmr_device_mock.async_wait_for_can_play.reset_mock()
    dmr_device_mock.async_play.reset_mock()
    await hass.services.async_call(
        MP_DOMAIN,
        mp_const.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp_const.ATTR_MEDIA_CONTENT_TYPE: mp_const.MEDIA_TYPE_MUSIC,
            mp_const.ATTR_MEDIA_CONTENT_ID: "http://192.88.99.20:8200/MediaItems/17621.mp3",
            mp_const.ATTR_MEDIA_ENQUEUE: False,
        },
        blocking=True,
    )
    dmr_device_mock.async_stop.assert_awaited_once_with()
    dmr_device_mock.async_set_transport_uri.assert_awaited_once_with(
        "http://192.88.99.20:8200/MediaItems/17621.mp3", "Home Assistant"
    )
    dmr_device_mock.async_wait_for_can_play.assert_awaited_once_with()
    dmr_device_mock.async_play.assert_awaited_once_with()

    # play_media again, while the device is already playing and can't stop
    dmr_device_mock.can_stop = False
    dmr_device_mock.transport_state = TransportState.PLAYING
    dmr_device_mock.async_stop.reset_mock()
    dmr_device_mock.async_set_transport_uri.reset_mock()
    dmr_device_mock.async_wait_for_can_play.reset_mock()
    dmr_device_mock.async_play.reset_mock()
    await hass.services.async_call(
        MP_DOMAIN,
        mp_const.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: mock_entity_id,
            mp_const.ATTR_MEDIA_CONTENT_TYPE: mp_const.MEDIA_TYPE_MUSIC,
            mp_const.ATTR_MEDIA_CONTENT_ID: "http://192.88.99.20:8200/MediaItems/17621.mp3",
            mp_const.ATTR_MEDIA_ENQUEUE: False,
        },
        blocking=True,
    )
    dmr_device_mock.async_stop.assert_not_awaited()
    dmr_device_mock.async_set_transport_uri.assert_awaited_once_with(
        "http://192.88.99.20:8200/MediaItems/17621.mp3", "Home Assistant"
    )
    dmr_device_mock.async_wait_for_can_play.assert_awaited_once_with()
    dmr_device_mock.async_play.assert_not_awaited()


async def test_unavailable_device(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
) -> None:
    """Test a DlnaDmrEntity with out a connected DmrDevice."""
    # Cause connection attempts to fail
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError

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
    # Check event notifiers are not aquired
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
    await async_update_entity(hass, mock_entity_id)
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    # Check attributes are unavailable
    attrs = mock_state.attributes
    for attr in ATTR_TO_PROPERTY:
        assert attr not in attrs

    assert attrs[ha_const.ATTR_FRIENDLY_NAME] == MOCK_DEVICE_NAME
    assert attrs[ha_const.ATTR_SUPPORTED_FEATURES] == 0

    # Check service calls do nothing
    SERVICES: list[tuple[str, dict]] = [
        (ha_const.SERVICE_VOLUME_SET, {mp_const.ATTR_MEDIA_VOLUME_LEVEL: 0.80}),
        (ha_const.SERVICE_VOLUME_MUTE, {mp_const.ATTR_MEDIA_VOLUME_MUTED: True}),
        (ha_const.SERVICE_MEDIA_PAUSE, {}),
        (ha_const.SERVICE_MEDIA_PLAY, {}),
        (ha_const.SERVICE_MEDIA_STOP, {}),
        (ha_const.SERVICE_MEDIA_NEXT_TRACK, {}),
        (ha_const.SERVICE_MEDIA_PREVIOUS_TRACK, {}),
        (ha_const.SERVICE_MEDIA_SEEK, {mp_const.ATTR_MEDIA_SEEK_POSITION: 33}),
        (
            mp_const.SERVICE_PLAY_MEDIA,
            {
                mp_const.ATTR_MEDIA_CONTENT_TYPE: mp_const.MEDIA_TYPE_MUSIC,
                mp_const.ATTR_MEDIA_CONTENT_ID: "http://192.88.99.20:8200/MediaItems/17621.mp3",
                mp_const.ATTR_MEDIA_ENQUEUE: False,
            },
        ),
    ]
    for service, data in SERVICES:
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: mock_entity_id, **data},
            blocking=True,
        )

    # Check hass device information has not been filled in yet
    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_device(identifiers={(DLNA_DOMAIN, MOCK_DEVICE_UDN)})
    assert device is None

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Confirm SSDP notifications unregistered
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Check event notifiers are not released
    domain_data_mock.async_release_event_notifier.assert_not_called()

    # Confirm the entity is still unavailable
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_become_available(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
) -> None:
    """Test a device becoming available after the entity is constructed."""
    # Cause connection attempts to fail before adding entity
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpConnectionError
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check hass device information has not been filled in yet
    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_device(identifiers={(DLNA_DOMAIN, MOCK_DEVICE_UDN)})
    assert device is None

    # Mock device is now available.
    domain_data_mock.upnp_factory.async_create_device.side_effect = None
    domain_data_mock.upnp_factory.async_create_device.reset_mock()

    # Send an SSDP notification from the now alive device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
        },
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Check device was created from the supplied URL
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        NEW_DEVICE_LOCATION
    )
    # Check event notifiers are aquired
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
    assert mock_state.state == ha_const.STATE_IDLE
    # Check hass device information is now filled in
    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_device(identifiers={(DLNA_DOMAIN, MOCK_DEVICE_UDN)})
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
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_alive_but_gone(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
) -> None:
    """Test a device sending an SSDP alive announcement, but not being connectable."""
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    # Send an SSDP notification from the still missing device
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
        },
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    # Device should still be unavailable
    mock_state = hass.states.get(mock_disconnected_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE


async def test_multiple_ssdp_alive(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    ssdp_scanner_mock: Mock,
    mock_disconnected_entity_id: str,
    dmr_device_mock: Mock,
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
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
        },
        ssdp.SsdpChange.ALIVE,
    )
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: NEW_DEVICE_LOCATION,
        },
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
    assert mock_state.state == media_player.STATE_IDLE


async def test_ssdp_byebye(
    hass: HomeAssistant,
    ssdp_scanner_mock: Mock,
    mock_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test device is disconnected when byebye is received."""
    # First byebye will cause a disconnect
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            "_udn": MOCK_DEVICE_UDN,
            "NTS": "ssdp:byebye",
        },
        ssdp.SsdpChange.BYEBYE,
    )

    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()

    # Device should be gone
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == media_player.STATE_IDLE

    # Second byebye will do nothing
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            "_udn": MOCK_DEVICE_UDN,
            "NTS": "ssdp:byebye",
        },
        ssdp.SsdpChange.BYEBYE,
    )

    dmr_device_mock.async_unsubscribe_services.assert_awaited_once()


async def test_ssdp_update(
    ssdp_scanner_mock: Mock,
    mock_entity_id: str,
    dmr_device_mock: Mock,
) -> None:
    """Test device does nothing when ssdp:update is received."""
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            "_udn": MOCK_DEVICE_UDN,
            "NTS": "ssdp:update",
            ssdp.ATTR_SSDP_BOOTID: "2",
        },
        ssdp.SsdpChange.UPDATE,
    )

    # Device was not reconnected, even with a new boot ID
    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1


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
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0]
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: MOCK_DEVICE_LOCATION,
            ssdp.ATTR_SSDP_BOOTID: "1",
        },
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 1
    assert dmr_device_mock.async_unsubscribe_services.call_count == 0

    # Send SSDP alive with same boot ID, nothing should happen
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: MOCK_DEVICE_LOCATION,
            ssdp.ATTR_SSDP_BOOTID: "1",
        },
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 1
    assert dmr_device_mock.async_unsubscribe_services.call_count == 0

    # Send a new SSDP alive with an incremented boot ID, device should be dis/reconnected
    await ssdp_callback(
        {
            ssdp.ATTR_SSDP_USN: MOCK_DEVICE_USN,
            ssdp.ATTR_SSDP_LOCATION: MOCK_DEVICE_LOCATION,
            ssdp.ATTR_SSDP_BOOTID: "2",
        },
        ssdp.SsdpChange.ALIVE,
    )
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    assert dmr_device_mock.async_subscribe_services.call_count == 2
    assert dmr_device_mock.async_unsubscribe_services.call_count == 1


async def test_become_unavailable(
    hass: HomeAssistant,
    domain_data_mock: Mock,
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
        MP_DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp_const.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
        blocking=True,
    )

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    # With a working connection, the state should be restored
    await async_update_entity(hass, mock_entity_id)
    dmr_device_mock.async_update.assert_any_call(do_ping=True)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    # Break the service again, and the connection too. An update will cause the
    # device to be disconnected
    dmr_device_mock.async_update.reset_mock()
    dmr_device_mock.async_update.side_effect = UpnpConnectionError

    await hass.services.async_call(
        MP_DOMAIN,
        ha_const.SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: mock_entity_id, mp_const.ATTR_MEDIA_VOLUME_LEVEL: 0.80},
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
    config_entry_mock.options = MappingProxyType(
        {
            CONF_POLL_AVAILABILITY: True,
        }
    )
    mock_entity_id = await setup_mock_component(hass, config_entry_mock)
    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_UNAVAILABLE

    # Check that an update will poll the device for availability
    domain_data_mock.upnp_factory.async_create_device.reset_mock()
    await async_update_entity(hass, mock_entity_id)
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
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    mock_state = hass.states.get(mock_entity_id)
    assert mock_state is not None
    assert mock_state.state == ha_const.STATE_IDLE

    # Clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }


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
    on_event(None, [])
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
    assert mock_state.state == ha_const.STATE_IDLE


async def test_config_update_connect_failure(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    dmr_device_mock: Mock,
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
    assert mock_state.state == ha_const.STATE_IDLE


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
    assert mock_state.state == ha_const.STATE_IDLE
