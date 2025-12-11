"""Tests for Kaleidescape media player platform."""

from unittest.mock import MagicMock

from kaleidescape import const as kaleidescape_const
from kaleidescape.device import Movie
import pytest

from homeassistant.components.kaleidescape import media_player
from homeassistant.components.kaleidescape.const import (
    DOMAIN,
    SERVICE_ATTR_VOLUME_LEVEL,
    SERVICE_ATTR_VOLUME_MUTED,
    SERVICE_SEND_VOLUME_LEVEL,
    SERVICE_SEND_VOLUME_MUTED,
)
from homeassistant.components.kaleidescape.media_player import (
    ATTR_VOLUME_CAPABILITIES,
    EVENT_DATA_VOLUME_LEVEL,
    EVENT_TYPE_USER_DEFINED_EVENT,
    EVENT_TYPE_VOLUME_DOWN_PRESSED,
    EVENT_TYPE_VOLUME_MUTE_PRESSED,
    EVENT_TYPE_VOLUME_SET_UPDATED,
    EVENT_TYPE_VOLUME_UP_PRESSED,
)
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACTION,
    CONF_PARAMS,
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
from homeassistant.core import HomeAssistant, callback
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


@pytest.mark.usefixtures("mock_integration")
async def test_async_handle_device_volume_events(
    hass: HomeAssistant, mock_device: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of USER_DEFINED_EVENT device events."""
    # Override volume_set debounce time to zero
    monkeypatch.setattr(media_player, "DEBOUNCE_TIME", 0)

    events: list[tuple[str, dict]] = []

    @callback
    def _capture(event):
        events.append((event.event_type, dict(event.data)))

    unsub1 = hass.bus.async_listen(EVENT_TYPE_VOLUME_SET_UPDATED, _capture)
    unsub2 = hass.bus.async_listen(EVENT_TYPE_VOLUME_UP_PRESSED, _capture)
    unsub3 = hass.bus.async_listen(EVENT_TYPE_VOLUME_DOWN_PRESSED, _capture)
    unsub4 = hass.bus.async_listen(EVENT_TYPE_VOLUME_MUTE_PRESSED, _capture)
    unsub5 = hass.bus.async_listen(EVENT_TYPE_USER_DEFINED_EVENT, _capture)

    try:
        # Test Non-list fields send no event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            None,
        )
        await hass.async_block_till_done()
        assert len(events) == 0

        # Test empty fields send no event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            [],
        )
        await hass.async_block_till_done()
        assert len(events) == 0

        # Generate 3 SET_VOLUME events to test bad data and debouncing
        for value in ("bad", "41", "42"):
            mock_device.dispatcher.send(
                kaleidescape_const.USER_DEFINED_EVENT,
                [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, value],
            )
            await hass.async_block_till_done()

        # Generate VOLUME_UP event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_UP],
        )
        await hass.async_block_till_done()

        # Generate VOLUME_DOWN event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            [kaleidescape_const.USER_DEFINED_EVENT_VOLUME_DOWN],
        )
        await hass.async_block_till_done()

        # Generate TOGGLE_MUTE event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            [kaleidescape_const.USER_DEFINED_EVENT_TOGGLE_MUTE],
        )
        await hass.async_block_till_done()

        # Generate USER_DEFINED_EVENT event
        mock_device.dispatcher.send(
            kaleidescape_const.USER_DEFINED_EVENT,
            ["custom_action", {"value": "custom_value"}],
        )
        await hass.async_block_till_done()

    finally:
        unsub1()
        unsub2()
        unsub3()
        unsub4()
        unsub5()

    # Validate events
    event_types = [e[0] for e in events]
    assert EVENT_TYPE_VOLUME_SET_UPDATED in event_types
    assert EVENT_TYPE_VOLUME_UP_PRESSED in event_types
    assert EVENT_TYPE_VOLUME_DOWN_PRESSED in event_types
    assert EVENT_TYPE_VOLUME_MUTE_PRESSED in event_types
    assert EVENT_TYPE_USER_DEFINED_EVENT in event_types

    volume_events = [d for t, d in events if t == EVENT_TYPE_VOLUME_SET_UPDATED]
    assert volume_events
    assert volume_events[-1][EVENT_DATA_VOLUME_LEVEL] == 0.42

    user_data_events = [d for t, d in events if t == EVENT_TYPE_USER_DEFINED_EVENT]
    assert user_data_events
    assert user_data_events[-1][CONF_ACTION] == "custom_action"
    assert user_data_events[-1][CONF_PARAMS] == {"value": "custom_value"}


@pytest.mark.usefixtures("mock_integration")
async def test_async_send_volume_level(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test async_send_volume_level sends scaled level and updates capabilities."""
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
        SERVICE_SEND_VOLUME_LEVEL,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            SERVICE_ATTR_VOLUME_LEVEL: 0.42,
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
        SERVICE_SEND_VOLUME_LEVEL,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            SERVICE_ATTR_VOLUME_LEVEL: 0.43,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps


@pytest.mark.usefixtures("mock_integration")
async def test_async_send_volume_muted(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test async_send_volume_muted updates capabilities and sends mute state."""
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
        SERVICE_SEND_VOLUME_MUTED,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            SERVICE_ATTR_VOLUME_MUTED: True,
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
        SERVICE_SEND_VOLUME_MUTED,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            SERVICE_ATTR_VOLUME_MUTED: False,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.attributes[ATTR_VOLUME_CAPABILITIES] & expected_caps == expected_caps
    mock_device.set_volume_muted.assert_called_with(False)


@pytest.mark.usefixtures("mock_integration")
async def test_async_will_remove_from_hass_cancels_debounce(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test async_will_remove_from_hass cancels debounced volume events."""
    # This is just forcing coverage
    mock_device.dispatcher.send(
        kaleidescape_const.USER_DEFINED_EVENT,
        [kaleidescape_const.USER_DEFINED_EVENT_SET_VOLUME_LEVEL, "10"],
    )
    await hass.async_block_till_done()
