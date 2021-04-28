"""Test songpal media_player."""
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, call, patch

from songpal import (
    ConnectChange,
    ContentChange,
    PowerChange,
    SongpalException,
    VolumeChange,
)

from homeassistant.components import media_player, songpal
from homeassistant.components.songpal.const import SET_SOUND_SETTING
from homeassistant.components.songpal.media_player import SUPPORT_SONGPAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    CONF_DATA,
    CONF_ENDPOINT,
    CONF_NAME,
    ENDPOINT,
    ENTITY_ID,
    FRIENDLY_NAME,
    MAC,
    MODEL,
    SW_VERSION,
    _create_mocked_device,
    _patch_media_player_device,
)

from tests.common import MockConfigEntry, async_fire_time_changed


def _get_attributes(hass):
    state = hass.states.get(ENTITY_ID)
    return state.as_dict()["attributes"]


async def test_setup_platform(hass):
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


async def test_setup_failed(hass, caplog):
    """Test failed to set up the entity."""
    mocked_device = _create_mocked_device(throw_exception=True)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    all_states = hass.states.async_all()
    assert len(all_states) == 0
    warning_records = [x for x in caplog.records if x.levelno == logging.WARNING]
    assert len(warning_records) == 2
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


async def test_state(hass):
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
    assert attributes["supported_features"] == SUPPORT_SONGPAL

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(songpal.DOMAIN, MAC)})
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert device.manufacturer == "Sony Corporation"
    assert device.name == FRIENDLY_NAME
    assert device.sw_version == SW_VERSION
    assert device.model == MODEL

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == MAC


async def test_services(hass):
    """Test services."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async def _call(service, **argv):
        await hass.services.async_call(
            media_player.DOMAIN,
            service,
            {"entity_id": ENTITY_ID, **argv},
            blocking=True,
        )

    await _call(media_player.SERVICE_TURN_ON)
    await _call(media_player.SERVICE_TURN_OFF)
    await _call(media_player.SERVICE_TOGGLE)
    assert mocked_device.set_power.call_count == 3
    mocked_device.set_power.assert_has_calls([call(True), call(False), call(False)])

    await _call(media_player.SERVICE_VOLUME_SET, volume_level=0.6)
    await _call(media_player.SERVICE_VOLUME_UP)
    await _call(media_player.SERVICE_VOLUME_DOWN)
    assert mocked_device.volume1.set_volume.call_count == 3
    mocked_device.volume1.set_volume.assert_has_calls([call(60), call(51), call(49)])

    await _call(media_player.SERVICE_VOLUME_MUTE, is_volume_muted=True)
    mocked_device.volume1.set_mute.assert_called_once_with(True)

    await _call(media_player.SERVICE_SELECT_SOURCE, source="none")
    mocked_device.input1.activate.assert_not_called()
    await _call(media_player.SERVICE_SELECT_SOURCE, source="title1")
    mocked_device.input1.activate.assert_called_once()

    await hass.services.async_call(
        songpal.DOMAIN,
        SET_SOUND_SETTING,
        {"entity_id": ENTITY_ID, "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device.set_sound_settings.reset_mock()

    mocked_device2 = _create_mocked_device()
    sys_info = MagicMock()
    sys_info.macAddr = "mac2"
    sys_info.version = SW_VERSION
    type(mocked_device2).get_system_info = AsyncMock(return_value=sys_info)
    entry2 = MockConfigEntry(
        domain=songpal.DOMAIN, data={CONF_NAME: "d2", CONF_ENDPOINT: ENDPOINT}
    )
    entry2.add_to_hass(hass)
    with _patch_media_player_device(mocked_device2):
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        songpal.DOMAIN,
        SET_SOUND_SETTING,
        {"entity_id": "all", "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device2.set_sound_settings.assert_called_once_with("name", "value")


async def test_websocket_events(hass):
    """Test websocket events."""
    mocked_device = _create_mocked_device()
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_media_player_device(mocked_device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mocked_device.listen_notifications.assert_called_once()
    assert mocked_device.on_notification.call_count == 4

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

    power_change = MagicMock()
    power_change.status = False
    await notification_callbacks[PowerChange](power_change)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_disconnected(hass, caplog):
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
