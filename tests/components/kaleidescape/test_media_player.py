"""Tests for Kaleidescape media player platform."""

from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const
from kaleidescape.device import Movie
import pytest

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
    mock_device.dispatcher.send(kaleidescape_const.DEVICE_POWER_STATE)
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
    mock_device.dispatcher.send(kaleidescape_const.PLAY_STATUS)
    await hass.async_block_till_done()
    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_PLAYING

    # Devices pauses playing
    mock_device.movie.play_status = kaleidescape_const.PLAY_STATUS_PAUSED
    mock_device.dispatcher.send(kaleidescape_const.PLAY_STATUS)
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
    assert device.name == FRIENDLY_NAME
    assert device.model == "Strato"
    assert device.sw_version == "10.4.2-19218"
    assert device.manufacturer == "Kaleidescape"
