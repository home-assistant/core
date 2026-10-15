"""Tests for the LG TV RS-232 media player platform."""

from pathlib import Path
from unittest.mock import call

from freezegun.api import FrozenDateTimeFactory
from lg_rs232_tv import CommandRejected, InputSource, PowerState, TVState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lg_tv_rs232.media_player import (
    INPUT_SOURCE_LG_TO_HA,
    SCAN_INTERVAL,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import load_json

from .conftest import MockLGTV, _default_state

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "media_player.lg_tv"


@pytest.fixture(autouse=True)
async def auto_init_components(init_components: None) -> None:
    """Set up the component."""


async def test_entities_created(
    hass: HomeAssistant,
    mock_lgtv: MockLGTV,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the media player entity is created through config entry setup."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_lgtv.query.assert_awaited()


async def test_polling_updates_state(
    hass: HomeAssistant, mock_lgtv: MockLGTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test the entity polls the TV on the scan interval and reflects changes."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    off_state = _default_state()
    off_state.power = PowerState.OFF
    mock_lgtv.query.side_effect = lambda _attrs: mock_lgtv.mock_state(off_state)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_lgtv.query.assert_awaited()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_state_updates(hass: HomeAssistant, mock_lgtv: MockLGTV) -> None:
    """Test the entity updates from TV pushes and disconnects."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    state = _default_state()
    state.power = PowerState.OFF
    mock_lgtv.mock_state(state)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_lgtv.mock_state(None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_state_unknown_when_not_queried(
    hass: HomeAssistant, mock_lgtv: MockLGTV
) -> None:
    """Test attributes are cleared when the TV reports no state."""
    mock_lgtv.mock_state(TVState())
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None


async def test_power_controls(hass: HomeAssistant, mock_lgtv: MockLGTV) -> None:
    """Test power services call the right methods."""
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_lgtv.power_on.assert_awaited_once()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_lgtv.power_off.assert_awaited_once()


async def test_volume_controls(hass: HomeAssistant, mock_lgtv: MockLGTV) -> None:
    """Test volume state and controls."""
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    assert mock_lgtv.set_volume.await_args == call(50)

    # Volume up/down use the media player base class default step.
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert mock_lgtv.set_volume.await_args == call(30)

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert mock_lgtv.set_volume.await_args == call(10)


async def test_mute_controls(hass: HomeAssistant, mock_lgtv: MockLGTV) -> None:
    """Test mute state and controls."""
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_lgtv.mute_on.assert_awaited_once()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_lgtv.mute_off.assert_awaited_once()


async def test_volume_features_depend_on_speaker_output(
    hass: HomeAssistant, mock_lgtv: MockLGTV
) -> None:
    """Test volume features are dropped when the TV speaker is not the output.

    The TV only answers the balance query when its own speaker is the active
    audio output, so balance availability gates the volume features.
    """
    features = hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
    assert features & MediaPlayerEntityFeature.VOLUME_SET
    assert features & MediaPlayerEntityFeature.VOLUME_STEP
    assert features & MediaPlayerEntityFeature.VOLUME_MUTE

    state = _default_state()
    state.balance = None
    mock_lgtv.mock_state(state)
    await hass.async_block_till_done()

    entity_state = hass.states.get(ENTITY_ID)
    features = entity_state.attributes[ATTR_SUPPORTED_FEATURES]
    assert not features & MediaPlayerEntityFeature.VOLUME_SET
    assert not features & MediaPlayerEntityFeature.VOLUME_STEP
    assert not features & MediaPlayerEntityFeature.VOLUME_MUTE
    assert features & MediaPlayerEntityFeature.SELECT_SOURCE

    # The volume attributes are dropped along with the controls.
    assert ATTR_MEDIA_VOLUME_LEVEL not in entity_state.attributes
    assert ATTR_MEDIA_VOLUME_MUTED not in entity_state.attributes


async def test_source_state_and_controls(
    hass: HomeAssistant, mock_lgtv: MockLGTV
) -> None:
    """Test source state and selection."""
    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state.attributes[ATTR_INPUT_SOURCE] == "hdmi1"

    source_list = entity_state.attributes[ATTR_INPUT_SOURCE_LIST]
    assert "hdmi1" in source_list
    assert "av1" in source_list
    assert source_list == sorted(source_list)

    state = _default_state()
    state.input_source = InputSource.HDMI2
    mock_lgtv.mock_state(state)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE] == "hdmi2"

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "hdmi3"},
        blocking=True,
    )
    assert mock_lgtv.select_input_source.await_args == call(InputSource.HDMI3)


@pytest.mark.parametrize(
    "exception",
    [CommandRejected("a", "02"), ConnectionError("connection lost"), TimeoutError],
)
async def test_command_error_raises(
    hass: HomeAssistant, mock_lgtv: MockLGTV, exception: Exception
) -> None:
    """Test library errors raised during an action surface as HomeAssistantError."""
    mock_lgtv.power_on.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )


def test_input_source_translation_keys_cover_all_enum_members() -> None:
    """Test all input sources have a declared translation key."""
    assert set(INPUT_SOURCE_LG_TO_HA) == set(InputSource)

    strings = load_json(Path("homeassistant/components/lg_tv_rs232/strings.json"))
    assert set(INPUT_SOURCE_LG_TO_HA.values()) == set(
        strings["entity"]["media_player"]["tv"]["state_attributes"]["source"]["state"]
    )
