"""Test songpal media_player."""
import pytest
from songpal import (
    ConnectChange,
    ContentChange,
    PowerChange,
    SongpalException,
    VolumeChange,
)

from homeassistant.components import songpal
from homeassistant.components.songpal.const import SET_SOUND_SETTING
from homeassistant.components.songpal.media_player import (
    STATE_OFF,
    STATE_ON,
    SUPPORT_SONGPAL,
    SongpalDevice,
    async_setup_entry,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import (
    CONF_DATA,
    CONF_ENDPOINT,
    CONF_NAME,
    ENDPOINT,
    FRIENDLY_NAME,
    MAC,
    MODEL,
    SW_VERSION,
    _create_mocked_device,
    _patch_media_player_device,
)

from tests.async_mock import AsyncMock, MagicMock, call, patch
from tests.common import MockConfigEntry


async def test_setup_platform(hass):
    """Test the legacy setup platform."""
    mocked_device = _create_mocked_device(throw_exception=True)
    with _patch_media_player_device(mocked_device):
        await async_setup_component(
            hass,
            "media_player",
            {
                "media_player": [
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


async def test_setup_failed(hass):
    """Test failed to set up the entity."""
    mocked_device = _create_mocked_device(throw_exception=True)
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    mocked_add_entity = MagicMock()

    with _patch_media_player_device(mocked_device), pytest.raises(PlatformNotReady):
        await async_setup_entry(hass, entry, mocked_add_entity)
    mocked_add_entity.assert_not_called()


async def test_properties(hass):
    """Test property values."""
    mocked_device = _create_mocked_device()

    songpal_device = SongpalDevice(FRIENDLY_NAME, mocked_device)
    songpal_device.hass = hass
    await songpal_device.async_update()
    await hass.async_block_till_done()

    assert songpal_device.should_poll is False
    assert songpal_device.name == FRIENDLY_NAME
    assert songpal_device.unique_id == MAC
    assert songpal_device.device_info == {
        "connections": {(dr.CONNECTION_NETWORK_MAC, MAC)},
        "identifiers": {(songpal.DOMAIN, MAC)},
        "manufacturer": "Sony Corporation",
        "name": FRIENDLY_NAME,
        "sw_version": SW_VERSION,
        "model": MODEL,
    }
    assert songpal_device.available is True
    assert songpal_device.source_list == ["title1", "title2"]
    assert songpal_device.state == STATE_ON
    assert songpal_device.source == "title2"
    assert songpal_device.volume_level == 0.5
    assert songpal_device.is_volume_muted is False
    assert songpal_device.supported_features == SUPPORT_SONGPAL

    # no volume
    type(mocked_device).get_volume_information = AsyncMock(return_value=[])
    await songpal_device.async_update()
    assert songpal_device.available is False

    # multiple volumes
    volume1 = mocked_device.volume1
    volume2 = MagicMock()
    type(mocked_device).get_volume_information = AsyncMock(
        return_value=[volume1, volume2]
    )
    await songpal_device.async_update()
    assert songpal_device.available is True
    assert songpal_device._volume_control == volume1  # pylint: disable=protected-access

    # exception
    type(mocked_device).get_power = AsyncMock(side_effect=SongpalException("exception"))
    await songpal_device.async_update()
    assert songpal_device.available is False


async def test_methods(hass):
    """Test method calls."""
    mocked_device = _create_mocked_device()

    songpal_device = SongpalDevice(FRIENDLY_NAME, mocked_device)
    songpal_device.hass = hass
    await songpal_device.async_update()
    await hass.async_block_till_done()

    await songpal_device.async_select_source("none")
    mocked_device.input1.activate.assert_not_called()
    await songpal_device.async_select_source("title1")
    mocked_device.input1.activate.assert_called_once()

    await songpal_device.async_set_volume_level(0.6)
    await songpal_device.async_volume_up()
    await songpal_device.async_volume_down()
    assert mocked_device.volume1.set_volume.call_count == 3
    mocked_device.volume1.set_volume.assert_has_calls(
        [call(60), call("+1"), call("-1")]
    )

    await songpal_device.async_turn_on()
    await songpal_device.async_turn_off()
    assert mocked_device.set_power.call_count == 2
    mocked_device.set_power.assert_has_calls([call(True), call(False)])

    await songpal_device.async_mute_volume(True)
    mocked_device.volume1.set_mute.assert_called_once_with(True)


async def test_services(hass):
    """Test custom services."""
    MockConfigEntry(
        domain=songpal.DOMAIN, data={CONF_NAME: "d1", CONF_ENDPOINT: ENDPOINT}
    ).add_to_hass(hass)
    mocked_device = _create_mocked_device()

    with _patch_media_player_device(mocked_device):
        await async_setup_component(hass, songpal.DOMAIN, {})
        await hass.async_block_till_done()

    await hass.services.async_call(
        songpal.DOMAIN,
        SET_SOUND_SETTING,
        {"entity_id": "media_player.d1", "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")
    mocked_device.set_sound_settings.reset_mock()
    await hass.services.async_call(
        songpal.DOMAIN,
        SET_SOUND_SETTING,
        {"entity_id": "all", "name": "name", "value": "value"},
        blocking=True,
    )
    mocked_device.set_sound_settings.assert_called_once_with("name", "value")


async def test_websocket_events(hass):
    """Test websocket events."""
    mocked_device = _create_mocked_device()

    songpal_device = SongpalDevice(FRIENDLY_NAME, mocked_device)
    songpal_device.hass = hass
    songpal_device.async_write_ha_state = MagicMock()
    songpal_device.async_update_ha_state = AsyncMock()
    await songpal_device.async_update()
    await hass.async_block_till_done()

    mocked_device.listen_notifications.assert_called_once()
    assert mocked_device.on_notification.call_count == 4

    notification_callbacks = mocked_device.notification_callbacks

    volume_change = MagicMock()
    volume_change.mute = True
    volume_change.volume = 20
    await notification_callbacks[VolumeChange](volume_change)
    assert songpal_device.is_volume_muted is True
    assert songpal_device.volume_level == 0.2
    songpal_device.async_write_ha_state.assert_called_once()
    songpal_device.async_write_ha_state.reset_mock()

    content_change = MagicMock()
    content_change.is_input = False
    content_change.uri = "uri1"
    await notification_callbacks[ContentChange](content_change)
    assert songpal_device.source == "title2"
    songpal_device.async_write_ha_state.assert_not_called()
    content_change.is_input = True
    await notification_callbacks[ContentChange](content_change)
    assert songpal_device.source == "title1"
    songpal_device.async_write_ha_state.assert_called_once()
    songpal_device.async_write_ha_state.reset_mock()

    power_change = MagicMock()
    power_change.status = False
    await notification_callbacks[PowerChange](power_change)
    assert songpal_device.state == STATE_OFF
    songpal_device.async_write_ha_state.assert_called_once()
    songpal_device.async_write_ha_state.reset_mock()

    connect_change = MagicMock()
    connect_change.exception = "disconnected"

    async def _mocked_sleep(delay):
        songpal_device._available = True  # pylint: disable=protected-access

    with patch("asyncio.sleep", side_effect=_mocked_sleep) as sleep:
        await notification_callbacks[ConnectChange](connect_change)
    sleep.assert_called_once()
    mocked_device.clear_notification_callbacks.assert_called_once()
    songpal_device.async_update_ha_state.assert_called_once_with(force_refresh=True)
