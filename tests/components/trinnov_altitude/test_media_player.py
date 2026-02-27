"""Tests for Trinnov Altitude media player platform."""

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import MOCK_ID

from tests.common import MockConfigEntry

ENTITY_ID = f"media_player.trinnov_altitude_{MOCK_ID}"


async def test_entity(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test entity attributes and state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.PLAYING


async def test_commands(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test media player service calls."""

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_device.power_on.assert_called_once_with()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_device.power_off.assert_called_once_with()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, "is_volume_muted": True},
        blocking=True,
    )
    mock_device.mute_set.assert_called_once_with(True)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.35},
        blocking=True,
    )
    mock_device.volume_percentage_set.assert_called_once_with(35.0)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_device.volume_up.assert_called_once_with()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_device.volume_down.assert_called_once_with()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, "source": "Apple TV"},
        blocking=True,
    )
    mock_device.source_set_by_name.assert_called_once_with("Apple TV")


async def test_state_off_when_not_synced(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test state is OFF when disconnected/unsynced."""
    mock_device.connected = False
    mock_device.state.synced = False

    callback = mock_device.register_callback.call_args[0][0]
    callback("received_message", None)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
