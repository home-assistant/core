"""Tests for Kaleidescape media player platform."""

from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const
from kaleidescape.device import Movie
import pytest

from homeassistant.components.kaleidescape.const import DOMAIN
from homeassistant.components.kaleidescape.media_player import ATTR_VOLUME_CAPABILITIES
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL

ENTITY_ID = f"media_player.kaleidescape_device_{MOCK_SERIAL}"
FRIENDLY_NAME = f"Kaleidescape Device {MOCK_SERIAL}"


@pytest.mark.usefixtures("mock_device", "mock_integration")
async def test_entity(hass: HomeAssistant) -> None:
    """Test entity attributes."""
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_OFF
    assert entity.attributes["friendly_name"] == FRIENDLY_NAME


@pytest.mark.usefixtures("mock_integration")
async def test_update_state(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Tests dispatched signals update player."""
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_OFF

    # Device turns on
    mock_device.power.state = kaleidescape_const.DEVICE_POWER_STATE_ON
    mock_device.dispatcher.send(kaleidescape_const.DEVICE_POWER_STATE, [])
    await hass.async_block_till_done()
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_IDLE

    # Devices starts playing
    mock_device.movie = Movie(
        handle="handle",
        title="title",
        cover="cover",
        cover_hires="cover_hires",
        rating="rating",
        rating_reason="rating_reason",
        year="year",
        runtime="runtime",
        actors=[],
        director="director",
        directors=[],
        genre="genre",
        genres=[],
        synopsis="synopsis",
        color="color",
        country="country",
        aspect_ratio="aspect_ratio",
        media_type="media_type",
        play_status=kaleidescape_const.PLAY_STATUS_PLAYING,
        play_speed=1,
        title_number=1,
        title_length=1,
        title_location=1,
        chapter_number=1,
        chapter_length=1,
        chapter_location=1,
    )
    mock_device.dispatcher.send(kaleidescape_const.PLAY_STATUS, [])
    await hass.async_block_till_done()
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_PLAYING

    # Devices pauses playing
    mock_device.movie.play_status = kaleidescape_const.PLAY_STATUS_PAUSED
    mock_device.dispatcher.send(kaleidescape_const.PLAY_STATUS, [])
    await hass.async_block_till_done()
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_PAUSED


@pytest.mark.usefixtures("mock_integration")
async def test_services(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Test service calls."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.leave_standby.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.enter_standby.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.play.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.pause.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.stop.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.next.call_count == 1

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.previous.call_count == 1


@pytest.mark.usefixtures("mock_device", "mock_integration")
async def test_device(device_registry: dr.DeviceRegistry) -> None:
    """Test device attributes."""
    device = device_registry.async_get_device(
        identifiers={("kaleidescape", MOCK_SERIAL)}
    )
    assert device
    assert device.name == FRIENDLY_NAME
    assert device.model == "Strato"
    assert device.sw_version == "10.4.2-19218"
    assert device.manufacturer == "Kaleidescape"


@pytest.mark.usefixtures("mock_integration")
async def test_async_handle_device_volume_query_event(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test USER_DEFINED_EVENT_VOLUME_QUERY updates volume capabilities."""
    baseline_caps = (
        kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_CONTROL
        | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
    )

    assert mock_device.set_volume_capabilities.call_count == 0

    # First VOLUME_QUERY should send baseline capabilities when none are set
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()

    assert mock_device.set_volume_capabilities.call_count == 1
    first_call_caps = mock_device.set_volume_capabilities.call_args_list[0].args[0]
    assert first_call_caps == baseline_caps

    # Second VOLUME_QUERY should still send capabilities (force=True)
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_QUERY],
    )
    await hass.async_block_till_done()

    assert mock_device.set_volume_capabilities.call_count == 2
    second_call_caps = mock_device.set_volume_capabilities.call_args_list[1].args[0]
    assert second_call_caps == baseline_caps

    # Test empty params are ignored
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [],
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_integration")
async def test_async_set_volume_level(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test test_async_set_volume_level sends scaled level and updates capabilities."""
    expected_caps = (
        kaleidescape_const.VOLUME_CAPABILITIES_SET_VOLUME
        | kaleidescape_const.VOLUME_CAPABILITIES_VOLUME_FEEDBACK
    )

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert (
        entity.attributes[ATTR_VOLUME_CAPABILITIES]
        == kaleidescape_const.VOLUME_CAPABILITIES_NONE
    )

    # Test service call sets capabilities and sends volume level
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_VOLUME_LEVEL: 0.42,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps

    # Test 2nd service call with runs without updating capabilities again
    mock_device.set_volume_capabilities.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_VOLUME_LEVEL: 0.43,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps


@pytest.mark.usefixtures("mock_integration")
async def test_async_mute_volume(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Test test_async_mute_volume updates capabilities and sends mute state."""
    expected_caps = (
        kaleidescape_const.VOLUME_CAPABILITIES_MUTE_CONTROL
        | kaleidescape_const.VOLUME_CAPABILITIES_MUTE_FEEDBACK
    )

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert (
        entity.attributes[ATTR_VOLUME_CAPABILITIES]
        == kaleidescape_const.VOLUME_CAPABILITIES_NONE
    )

    # Test service call sets capabilities and sends mute state
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps
    mock_device.set_volume_muted.assert_called_with(True)

    # Test 2nd service call runs without updating capabilities again
    mock_device.set_volume_capabilities.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_VOLUME_MUTED: False,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps
    mock_device.set_volume_muted.assert_called_with(False)
