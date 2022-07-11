"""Tests for the HDMI-CEC media player platform."""
from pycec.const import (
    DEVICE_TYPE_NAMES,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
    TYPE_AUDIO,
    TYPE_PLAYBACK,
    TYPE_RECORDER,
    TYPE_TUNER,
    TYPE_TV,
    TYPE_UNKNOWN,
)
import pytest

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntityFeature as MPEF,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
)

from tests.components.hdmi_cec import MockHDMIDevice, assert_key_press_release


@pytest.fixture(
    params=[
        False,
        pytest.param(
            True,
            marks=pytest.mark.xfail(
                reason="The entity is missing the `schedule_update_ha_state` for a correct push entity."
            ),
        ),
    ],
    ids=["skip_assert_state", "run_assert_state"],
)
def assert_state(hass, request):
    """Allow for skipping the assert state changes.

    This is broken in this entity, but we still want to test that
    the rest of the code works as expected.
    """

    def test_state(state, expected):
        if request.param:
            assert state == expected
        else:
            assert True

    return test_state


async def test_load_platform(hass, create_hdmi_network, create_cec_entity):
    """Test that media_player entity is loaded."""
    hdmi_network = await create_hdmi_network(config={"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_3")
    assert state is not None

    state = hass.states.get("switch.hdmi_3")
    assert state is None


@pytest.mark.parametrize("platform", [{}, {"platform": "switch"}])
async def test_load_types(hass, create_hdmi_network, create_cec_entity, platform):
    """Test that media_player entity is loaded when types is set."""
    config = platform | {"types": {"hdmi_cec.hdmi_4": "media_player"}}
    hdmi_network = await create_hdmi_network(config=config)
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_3")
    assert state is None

    state = hass.states.get("switch.hdmi_3")
    assert state is not None

    mock_hdmi_device = MockHDMIDevice(logical_address=4)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_4")
    assert state is not None

    state = hass.states.get("switch.hdmi_4")
    assert state is None


async def test_service_on(hass, create_hdmi_network, create_cec_entity, assert_state):
    """Test that media_player triggers on `on` service."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    state = hass.states.get("media_player.hdmi_3")
    assert state.state != STATE_ON

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.hdmi_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_hdmi_device.turn_on.assert_called_once_with()

    state = hass.states.get("media_player.hdmi_3")
    assert_state(state.state, STATE_ON)


async def test_service_off(hass, create_hdmi_network, create_cec_entity, assert_state):
    """Test that media_player triggers on `off` service."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    state = hass.states.get("media_player.hdmi_3")
    assert state.state != STATE_OFF

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.hdmi_3"},
        blocking=True,
    )

    mock_hdmi_device.turn_off.assert_called_once_with()

    state = hass.states.get("media_player.hdmi_3")
    assert_state(state.state, STATE_OFF)


@pytest.mark.parametrize(
    "type_id,expected_features",
    [
        (TYPE_TV, MPEF.TURN_ON | MPEF.TURN_OFF),
        (
            TYPE_RECORDER,
            MPEF.TURN_ON
            | MPEF.TURN_OFF
            | MPEF.PLAY_MEDIA
            | MPEF.PAUSE
            | MPEF.STOP
            | MPEF.PREVIOUS_TRACK
            | MPEF.NEXT_TRACK,
        ),
        (TYPE_UNKNOWN, MPEF.TURN_ON | MPEF.TURN_OFF),
        pytest.param(
            TYPE_TUNER,
            MPEF.TURN_ON | MPEF.TURN_OFF | MPEF.PLAY_MEDIA | MPEF.PAUSE | MPEF.STOP,
            marks=pytest.mark.xfail(
                reason="Checking for the wrong attribute, should be checking `type_id`, is checking `type`."
            ),
        ),
        pytest.param(
            TYPE_PLAYBACK,
            MPEF.TURN_ON
            | MPEF.TURN_OFF
            | MPEF.PLAY_MEDIA
            | MPEF.PAUSE
            | MPEF.STOP
            | MPEF.PREVIOUS_TRACK
            | MPEF.NEXT_TRACK,
            marks=pytest.mark.xfail(
                reason="Checking for the wrong attribute, should be checking `type_id`, is checking `type`."
            ),
        ),
        (
            TYPE_AUDIO,
            MPEF.TURN_ON | MPEF.TURN_OFF | MPEF.VOLUME_STEP | MPEF.VOLUME_MUTE,
        ),
    ],
)
async def test_supported_features(
    hass, create_hdmi_network, create_cec_entity, type_id, expected_features
):
    """Test that features load as expected."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(
        logical_address=3, type=type_id, type_name=DEVICE_TYPE_NAMES[type_id]
    )
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("media_player.hdmi_3")
    assert state.attributes["supported_features"] == expected_features


@pytest.mark.parametrize(
    "service,key",
    [
        (SERVICE_VOLUME_DOWN, KEY_VOLUME_DOWN),
        (SERVICE_VOLUME_UP, KEY_VOLUME_UP),
    ],
)
async def test_audio_keypress_services(
    hass, create_hdmi_network, create_cec_entity, service, key
):
    """Test commands that do a keypress and don't return a state."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=TYPE_AUDIO)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "media_player.hdmi_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_hdmi_device.send_command.call_count == 2
    assert_key_press_release(mock_hdmi_device.send_command, dst=3, key=key)
