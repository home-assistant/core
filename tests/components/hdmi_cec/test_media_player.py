"""Tests for the HDMI-CEC media player platform."""

from collections.abc import Callable
from typing import Any

from pycec.const import (
    DEVICE_TYPE_NAMES,
    KEY_BACKWARD,
    KEY_FORWARD,
    KEY_MUTE_TOGGLE,
    KEY_PAUSE,
    KEY_PLAY,
    KEY_STOP,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
    POWER_OFF,
    POWER_ON,
    STATUS_PLAY,
    STATUS_STILL,
    STATUS_STOP,
    TYPE_AUDIO,
    TYPE_PLAYBACK,
    TYPE_RECORDER,
    TYPE_TUNER,
    TYPE_TV,
    TYPE_UNKNOWN,
)
import pytest

from homeassistant.components.hdmi_cec import EVENT_HDMI_CEC_UNAVAILABLE
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntityFeature as MPEF,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import MockHDMIDevice, assert_key_press_release
from .conftest import CecEntityCreator, HDMINetworkCreator

type AssertState = Callable[[str, str], None]


@pytest.fixture(
    name="assert_state",
    params=[
        False,
        pytest.param(
            True,
            marks=pytest.mark.xfail(
                reason="""State isn't updated because the function is missing the
                `schedule_update_ha_state` for a correct push entity. Would still
                update once the data comes back from the device."""
            ),
        ),
    ],
    ids=["skip_assert_state", "run_assert_state"],
)
def assert_state_fixture(request: pytest.FixtureRequest) -> AssertState:
    """Allow for skipping the assert state changes.

    This is broken in this entity, but we still want to test that
    the rest of the code works as expected.
    """

    def _test_state(state: str, expected: str) -> None:
        if request.param:
            assert state == expected
        else:
            assert True

    return _test_state


async def test_load_platform(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
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
async def test_load_types(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    platform: dict[str, Any],
) -> None:
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


async def test_service_on(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    assert_state: AssertState,
) -> None:
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


async def test_service_off(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    assert_state: AssertState,
) -> None:
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
    ("type_id", "expected_features"),
    [
        (TYPE_TV, (MPEF.TURN_ON, MPEF.TURN_OFF)),
        (
            TYPE_RECORDER,
            (
                MPEF.TURN_ON,
                MPEF.TURN_OFF,
                MPEF.PAUSE,
                MPEF.STOP,
                MPEF.PREVIOUS_TRACK,
                MPEF.NEXT_TRACK,
            ),
        ),
        pytest.param(
            TYPE_RECORDER,
            (MPEF.PLAY,),
            marks=pytest.mark.xfail(
                reason="The feature is wrongly set to PLAY_MEDIA, but should be PLAY."
            ),
        ),
        (TYPE_UNKNOWN, (MPEF.TURN_ON, MPEF.TURN_OFF)),
        pytest.param(
            TYPE_TUNER,
            (
                MPEF.TURN_ON,
                MPEF.TURN_OFF,
                MPEF.PAUSE,
                MPEF.STOP,
            ),
            marks=pytest.mark.xfail(
                reason="Checking for the wrong attribute, should be checking `type_id`, is checking `type`."
            ),
        ),
        pytest.param(
            TYPE_TUNER,
            (MPEF.PLAY,),
            marks=pytest.mark.xfail(
                reason="The feature is wrongly set to PLAY_MEDIA, but should be PLAY."
            ),
        ),
        pytest.param(
            TYPE_PLAYBACK,
            (
                MPEF.TURN_ON,
                MPEF.TURN_OFF,
                MPEF.PAUSE,
                MPEF.STOP,
                MPEF.PREVIOUS_TRACK,
                MPEF.NEXT_TRACK,
            ),
            marks=pytest.mark.xfail(
                reason="Checking for the wrong attribute, should be checking `type_id`, is checking `type`."
            ),
        ),
        pytest.param(
            TYPE_PLAYBACK,
            (MPEF.PLAY,),
            marks=pytest.mark.xfail(
                reason="The feature is wrongly set to PLAY_MEDIA, but should be PLAY."
            ),
        ),
        (
            TYPE_AUDIO,
            (
                MPEF.TURN_ON,
                MPEF.TURN_OFF,
                MPEF.VOLUME_STEP,
                MPEF.VOLUME_MUTE,
            ),
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    type_id: int,
    expected_features: MPEF,
) -> None:
    """Test that features load as expected."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(
        logical_address=3, type=type_id, type_name=DEVICE_TYPE_NAMES[type_id]
    )
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("media_player.hdmi_3")
    supported_features = state.attributes["supported_features"]
    for feature in expected_features:
        assert supported_features & feature


@pytest.mark.parametrize(
    ("service", "extra_data", "key"),
    [
        (SERVICE_VOLUME_DOWN, None, KEY_VOLUME_DOWN),
        (SERVICE_VOLUME_UP, None, KEY_VOLUME_UP),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, KEY_MUTE_TOGGLE),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": False}, KEY_MUTE_TOGGLE),
    ],
)
async def test_volume_services(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    service: str,
    extra_data: dict[str, Any] | None,
    key: int,
) -> None:
    """Test volume related commands."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=TYPE_AUDIO)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    data = {ATTR_ENTITY_ID: "media_player.hdmi_3"}
    if extra_data:
        data |= extra_data

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        data,
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_hdmi_device.send_command.call_count == 2
    assert_key_press_release(mock_hdmi_device.send_command, dst=3, key=key)


@pytest.mark.parametrize(
    ("service", "key"),
    [
        (SERVICE_MEDIA_NEXT_TRACK, KEY_FORWARD),
        (SERVICE_MEDIA_PREVIOUS_TRACK, KEY_BACKWARD),
    ],
)
async def test_track_change_services(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    service: str,
    key: int,
) -> None:
    """Test track change related commands."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=TYPE_RECORDER)
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


@pytest.mark.parametrize(
    ("service", "key", "expected_state"),
    [
        pytest.param(
            SERVICE_MEDIA_PLAY,
            KEY_PLAY,
            STATE_PLAYING,
            marks=pytest.mark.xfail(
                reason="The wrong feature is defined, should be PLAY, not PLAY_MEDIA"
            ),
        ),
        (SERVICE_MEDIA_PAUSE, KEY_PAUSE, STATE_PAUSED),
        (SERVICE_MEDIA_STOP, KEY_STOP, STATE_IDLE),
    ],
)
async def test_playback_services(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    assert_state: AssertState,
    service: str,
    key: int,
    expected_state: str,
) -> None:
    """Test playback related commands."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=TYPE_RECORDER)
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

    state = hass.states.get("media_player.hdmi_3")
    assert_state(state.state, expected_state)


@pytest.mark.xfail(reason="PLAY feature isn't enabled")
async def test_play_pause_service(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    assert_state: AssertState,
) -> None:
    """Test play pause service."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(
        logical_address=3, type=TYPE_RECORDER, status=STATUS_PLAY
    )
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: "media_player.hdmi_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_hdmi_device.send_command.call_count == 2
    assert_key_press_release(mock_hdmi_device.send_command, dst=3, key=KEY_PAUSE)

    state = hass.states.get("media_player.hdmi_3")
    assert_state(state.state, STATE_PAUSED)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: "media_player.hdmi_3"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_hdmi_device.send_command.call_count == 4
    assert_key_press_release(mock_hdmi_device.send_command, 1, dst=3, key=KEY_PLAY)


@pytest.mark.parametrize(
    ("type_id", "update_data", "expected_state"),
    [
        (TYPE_TV, {"power_status": POWER_OFF}, STATE_OFF),
        (TYPE_TV, {"power_status": 3}, STATE_OFF),
        (TYPE_TV, {"power_status": POWER_ON}, STATE_ON),
        (TYPE_TV, {"power_status": 4}, STATE_ON),
        (TYPE_TV, {"power_status": POWER_ON, "status": STATUS_PLAY}, STATE_ON),
        (TYPE_RECORDER, {"power_status": POWER_OFF, "status": STATUS_PLAY}, STATE_OFF),
        (
            TYPE_RECORDER,
            {"power_status": POWER_ON, "status": STATUS_PLAY},
            STATE_PLAYING,
        ),
        (TYPE_RECORDER, {"power_status": POWER_ON, "status": STATUS_STOP}, STATE_IDLE),
        (
            TYPE_RECORDER,
            {"power_status": POWER_ON, "status": STATUS_STILL},
            STATE_PAUSED,
        ),
        (TYPE_RECORDER, {"power_status": POWER_ON, "status": None}, STATE_UNKNOWN),
    ],
)
async def test_update_state(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    type_id: int,
    update_data: dict[str, Any],
    expected_state: str,
) -> None:
    """Test state updates work as expected."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=type_id)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    for att, val in update_data.items():
        setattr(mock_hdmi_device, att, val)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.hdmi_3")
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("data", "expected_state"),
    [
        ({"power_status": POWER_OFF}, STATE_OFF),
        ({"power_status": 3}, STATE_OFF),
        ({"power_status": POWER_ON, "type": TYPE_TV}, STATE_ON),
        ({"power_status": 4, "type": TYPE_TV}, STATE_ON),
        ({"power_status": POWER_ON, "type": TYPE_TV, "status": STATUS_PLAY}, STATE_ON),
        (
            {"power_status": POWER_OFF, "type": TYPE_RECORDER, "status": STATUS_PLAY},
            STATE_OFF,
        ),
        (
            {"power_status": POWER_ON, "type": TYPE_RECORDER, "status": STATUS_PLAY},
            STATE_PLAYING,
        ),
        (
            {"power_status": POWER_ON, "type": TYPE_RECORDER, "status": STATUS_STOP},
            STATE_IDLE,
        ),
        (
            {"power_status": POWER_ON, "type": TYPE_RECORDER, "status": STATUS_STILL},
            STATE_PAUSED,
        ),
        (
            {"power_status": POWER_ON, "type": TYPE_RECORDER, "status": None},
            STATE_UNKNOWN,
        ),
    ],
)
async def test_starting_state(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    data: dict[str, Any],
    expected_state: str,
) -> None:
    """Test starting states are set as expected."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3, **data)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    state = hass.states.get("media_player.hdmi_3")
    assert state.state == expected_state


@pytest.mark.xfail(
    reason="The code only sets the state to unavailable, doesn't set the `_attr_available` to false."
)
async def test_unavailable_status(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
    """Test entity goes into unavailable status when expected."""
    hdmi_network = await create_hdmi_network({"platform": "media_player"})
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    hass.bus.async_fire(EVENT_HDMI_CEC_UNAVAILABLE)

    state = hass.states.get("media_player.hdmi_3")
    assert state.state == STATE_UNAVAILABLE
