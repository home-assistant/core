"""Test the Panasonic Viera media player entity."""

from datetime import timedelta
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_pac_input_source(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test PAC inputs are exposed through the standard media player API."""
    state = hass.states.get("media_player.panasonic_viera_tv")
    assert state.attributes["source"] == "HDMI1"
    assert state.attributes["source_list"] == ["TV", "HDMI1", "HDMI2"]
    assert (
        state.attributes["supported_features"] & MediaPlayerEntityFeature.SELECT_SOURCE
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {"entity_id": state.entity_id, ATTR_INPUT_SOURCE: "HDMI2"},
        blocking=True,
    )
    mock_remote.set_input.assert_called_once_with("HDMI2")


async def test_media_player_handle_URLerror(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test remote handle URLError as Unavailable."""

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_ON

    # simulate timeout error
    mock_remote.get_mute = Mock(side_effect=URLError(None, None))

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_UNAVAILABLE


async def test_media_player_handle_HTTPError(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test remote handle HTTPError as Off."""

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_ON

    # simulate http badrequest
    mock_remote.get_mute = Mock(side_effect=HTTPError(None, 400, None, None, None))

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_OFF
