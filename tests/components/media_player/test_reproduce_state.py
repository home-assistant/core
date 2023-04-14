"""The tests for reproduction of state."""
import pytest

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.reproduce_state import async_reproduce_states
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import Context, HomeAssistant, State

from tests.common import async_mock_service

ENTITY_1 = "media_player.test1"
ENTITY_2 = "media_player.test2"


@pytest.mark.parametrize(
    ("service", "state", "supported_feature"),
    [
        (SERVICE_TURN_ON, STATE_ON, MediaPlayerEntityFeature.TURN_ON),
        (SERVICE_TURN_OFF, STATE_OFF, MediaPlayerEntityFeature.TURN_OFF),
        (SERVICE_MEDIA_PLAY, STATE_BUFFERING, MediaPlayerEntityFeature.PLAY),
        (SERVICE_MEDIA_PLAY, STATE_PLAYING, MediaPlayerEntityFeature.PLAY),
        (SERVICE_MEDIA_STOP, STATE_IDLE, MediaPlayerEntityFeature.STOP),
        (SERVICE_MEDIA_PAUSE, STATE_PAUSED, MediaPlayerEntityFeature.PAUSE),
    ],
)
async def test_state(hass: HomeAssistant, service, state, supported_feature) -> None:
    """Test that we can turn a state into a service call."""
    calls_1 = async_mock_service(hass, DOMAIN, service)
    if service != SERVICE_TURN_ON:
        async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    # Don't support the feature won't call the service
    hass.states.async_set(ENTITY_1, "something", {ATTR_SUPPORTED_FEATURES: 0})
    await async_reproduce_states(hass, [State(ENTITY_1, state)])

    await hass.async_block_till_done()
    assert len(calls_1) == 0

    hass.states.async_set(
        ENTITY_1, "something", {ATTR_SUPPORTED_FEATURES: supported_feature}
    )
    await async_reproduce_states(hass, [State(ENTITY_1, state)])
    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1}


async def test_turn_on_with_mode(hass: HomeAssistant) -> None:
    """Test that state with additional attributes call multiple services."""
    hass.states.async_set(
        ENTITY_1,
        "something",
        {
            ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        },
    )

    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_SELECT_SOUND_MODE)

    await async_reproduce_states(
        hass, [State(ENTITY_1, "on", {ATTR_SOUND_MODE: "dummy"})]
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1}

    assert len(calls_2) == 1
    assert calls_2[0].data == {"entity_id": ENTITY_1, ATTR_SOUND_MODE: "dummy"}


async def test_multiple_same_state(hass: HomeAssistant) -> None:
    """Test that multiple states with same state gets calls."""
    for entity in ENTITY_1, ENTITY_2:
        hass.states.async_set(
            entity,
            "something",
            {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON},
        )

    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    await async_reproduce_states(hass, [State(ENTITY_1, "on"), State(ENTITY_2, "on")])

    await hass.async_block_till_done()

    assert len(calls_1) == 2
    # order is not guaranteed
    assert any(call.data == {"entity_id": "media_player.test1"} for call in calls_1)
    assert any(call.data == {"entity_id": "media_player.test2"} for call in calls_1)


async def test_multiple_different_state(hass: HomeAssistant) -> None:
    """Test that multiple states with different state gets calls."""
    for entity in ENTITY_1, ENTITY_2:
        hass.states.async_set(
            entity,
            "something",
            {
                ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
            },
        )

    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await async_reproduce_states(hass, [State(ENTITY_1, "on"), State(ENTITY_2, "off")])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": "media_player.test1"}
    assert len(calls_2) == 1
    assert calls_2[0].data == {"entity_id": "media_player.test2"}


async def test_state_with_context(hass: HomeAssistant) -> None:
    """Test that context is forwarded."""
    hass.states.async_set(
        ENTITY_1,
        "something",
        {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON},
    )

    calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    context = Context()

    await async_reproduce_states(hass, [State(ENTITY_1, "on")], context=context)

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1}
    assert calls[0].context == context


async def test_attribute_no_state(hass: HomeAssistant) -> None:
    """Test that no state service call is made with none state."""
    hass.states.async_set(
        ENTITY_1,
        "something",
        {
            ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        },
    )

    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    calls_3 = async_mock_service(hass, DOMAIN, SERVICE_SELECT_SOUND_MODE)

    value = "dummy"

    await async_reproduce_states(
        hass, [State(ENTITY_1, None, {ATTR_SOUND_MODE: value})]
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 0
    assert len(calls_2) == 0
    assert len(calls_3) == 1
    assert calls_3[0].data == {"entity_id": ENTITY_1, ATTR_SOUND_MODE: value}


@pytest.mark.parametrize(
    ("service", "attribute", "supported_feature"),
    [
        (
            SERVICE_VOLUME_SET,
            ATTR_MEDIA_VOLUME_LEVEL,
            MediaPlayerEntityFeature.VOLUME_SET,
        ),
        (
            SERVICE_VOLUME_MUTE,
            ATTR_MEDIA_VOLUME_MUTED,
            MediaPlayerEntityFeature.VOLUME_MUTE,
        ),
        (
            SERVICE_SELECT_SOURCE,
            ATTR_INPUT_SOURCE,
            MediaPlayerEntityFeature.SELECT_SOURCE,
        ),
        (
            SERVICE_SELECT_SOUND_MODE,
            ATTR_SOUND_MODE,
            MediaPlayerEntityFeature.SELECT_SOUND_MODE,
        ),
    ],
)
async def test_attribute(
    hass: HomeAssistant, service, attribute, supported_feature
) -> None:
    """Test that service call is made for each attribute."""
    hass.states.async_set(
        ENTITY_1,
        "something",
        {ATTR_SUPPORTED_FEATURES: supported_feature},
    )

    calls_1 = async_mock_service(hass, DOMAIN, service)

    value = "dummy"

    await async_reproduce_states(hass, [State(ENTITY_1, None, {attribute: value})])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1, attribute: value}


async def test_play_media(hass: HomeAssistant) -> None:
    """Test playing media."""
    hass.states.async_set(
        ENTITY_1,
        "something",
        {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PLAY_MEDIA},
    )
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)

    value_1 = "dummy_1"
    value_2 = "dummy_2"

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {ATTR_MEDIA_CONTENT_TYPE: value_1, ATTR_MEDIA_CONTENT_ID: value_2},
            )
        ],
    )

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {
                    ATTR_MEDIA_CONTENT_TYPE: value_1,
                    ATTR_MEDIA_CONTENT_ID: value_2,
                },
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 2
    assert calls_1[0].data == {
        "entity_id": ENTITY_1,
        ATTR_MEDIA_CONTENT_TYPE: value_1,
        ATTR_MEDIA_CONTENT_ID: value_2,
    }

    assert calls_1[1].data == {
        "entity_id": ENTITY_1,
        ATTR_MEDIA_CONTENT_TYPE: value_1,
        ATTR_MEDIA_CONTENT_ID: value_2,
    }
