"""Tests for the Sony TV RS-232 media player platform."""

import asyncio
from datetime import timedelta
import logging
from pathlib import Path
from unittest.mock import call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from sony_tv_rs232 import (
    AnswerCode,
    CommandTimeoutError,
    ConnectionLostError,
    InputSource,
    PowerState,
    SonyCommandError,
    SoundMode,
    TVState,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.sony_tv_rs232.const import (
    POWER_ON_REFRESH_DELAY,
    SCAN_INTERVAL,
)
from homeassistant.components.sony_tv_rs232.media_player import (
    INPUT_SOURCE_SONY_TO_HA,
    SOUND_MODE_SONY_TO_HA,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import load_json

from .conftest import MockSonyTV, default_state

ENTITY_ID = "media_player.sony_tv"
POWER_ON_REFRESH = timedelta(seconds=POWER_ON_REFRESH_DELAY)


def _standby_state() -> TVState:
    state = default_state()
    state.power = PowerState.OFF
    return state


def _records(caplog: pytest.LogCaptureFixture, level: int, text: str) -> int:
    return sum(
        1
        for record in caplog.records
        if record.levelno == level and text in record.getMessage()
    )


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def auto_init_components(init_components: None) -> None:
    """Set up the component."""


async def test_entities_created(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the media player entity is created through config entry setup."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    # The connect handshake already queried the TV; the first refresh does not.
    mock_sony_tv.query_power.assert_not_awaited()


@pytest.mark.parametrize("initial_tv_state", [_standby_state()])
async def test_standby_poll_queries_power_only(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a TV in standby is only asked for its power state."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await _tick(hass, freezer, SCAN_INTERVAL)

    mock_sony_tv.query_power.assert_awaited_once()
    mock_sony_tv.query_input_source.assert_not_awaited()
    mock_sony_tv.query_volume.assert_not_awaited()
    mock_sony_tv.query_mute.assert_not_awaited()
    mock_sony_tv.query_sound_mode.assert_not_awaited()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_on_poll_queries_everything(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a TV that is on is polled for every attribute the entity shows.

    A query the model does not answer times out and keeps its last value.
    """
    mock_sony_tv.query_mute.side_effect = CommandTimeoutError("no answer")
    mock_sony_tv.state.volume = 35
    mock_sony_tv.state.sound_mode = SoundMode.CUSTOM

    await _tick(hass, freezer, SCAN_INTERVAL)

    mock_sony_tv.query_power.assert_awaited_once()
    mock_sony_tv.query_input_source.assert_awaited_once()
    mock_sony_tv.query_volume.assert_awaited_once()
    mock_sony_tv.query_mute.assert_awaited_once()
    mock_sony_tv.query_sound_mode.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.35
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes[ATTR_SOUND_MODE] == "custom"


async def test_poll_reflects_remote_changes(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a change made with the TV's own remote is picked up on the poll."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_sony_tv.state.power = PowerState.OFF

    await _tick(hass, freezer, SCAN_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_poll_failure_marks_unavailable_once_and_recovers(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unanswered power query makes the entity unavailable.

    The outage is logged once across consecutive failing polls, and the
    recovery once.
    """
    mock_sony_tv.query_power.side_effect = CommandTimeoutError("no answer")

    await _tick(hass, freezer, SCAN_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await _tick(hass, freezer, SCAN_INTERVAL)
    await _tick(hass, freezer, SCAN_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR, "Error fetching sony_tv_rs232 data") == 1

    mock_sony_tv.query_power.side_effect = lambda: mock_sony_tv.state.power

    await _tick(hass, freezer, SCAN_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert _records(caplog, logging.INFO, "Fetching sony_tv_rs232 data recovered") == 1


@pytest.mark.parametrize("supports_queries", [False])
async def test_set_only_tv_is_not_polled(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a consumer TV that ignores queries is never asked anything."""
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    await _tick(hass, freezer, SCAN_INTERVAL)
    await _tick(hass, freezer, SCAN_INTERVAL)

    mock_sony_tv.query_power.assert_not_awaited()
    mock_sony_tv.query_input_source.assert_not_awaited()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_link_drop_and_reconnect(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the entity follows the library's link notifications.

    A dropped link is logged once; the state the library pushes after its own
    reconnect restores availability and is logged once.
    """
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_sony_tv.mock_state(None)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_sony_tv.mock_state(None)
    await hass.async_block_till_done()
    assert _records(caplog, logging.ERROR, "Serial connection to the TV lost") == 1

    mock_sony_tv.mock_state(default_state())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert _records(caplog, logging.INFO, "Connection to sony_tv_rs232 restored") == 1


async def test_poll_while_disconnected_does_not_query(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a scheduled poll on a dropped link sends nothing and logs nothing new."""
    mock_sony_tv.mock_state(None)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await _tick(hass, freezer, SCAN_INTERVAL)

    mock_sony_tv.query_power.assert_not_awaited()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR, "sony_tv_rs232") == 1


async def test_push_during_poll_is_ignored(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a notification raised by the poll's own queries is not published.

    Every query reply notifies subscribers; publishing those mid-poll would
    show partial states. The poll's snapshot is what reaches the entity.
    """
    seen: list[str] = []

    def push_partial() -> InputSource:
        mock_sony_tv._deliver(TVState())
        seen.append(hass.states.get(ENTITY_ID).state)
        return mock_sony_tv.state.input_source

    mock_sony_tv.query_input_source.side_effect = push_partial

    await _tick(hass, freezer, SCAN_INTERVAL)

    assert seen == [STATE_ON]
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_deferred_notification_from_poll_is_not_published(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the library's deferred notify from a poll query stays inside the poll.

    A query reply notifies via call_soon; landing after the poll it would be
    taken for a push, which cancels any refresh queued behind the poll.
    """

    async def remote_mute() -> bool:
        mock_sony_tv._apply("audio_mute", True)
        return True

    mock_sony_tv.query_mute.side_effect = remote_mute
    coordinator = mock_config_entry.runtime_data

    with patch.object(
        coordinator,
        "async_set_updated_data",
        wraps=coordinator.async_set_updated_data,
    ) as pushed:
        await _tick(hass, freezer, SCAN_INTERVAL)
        # A deferred notify lands one loop turn after the poll task finishes.
        await asyncio.sleep(0)
        await hass.async_block_till_done()

    pushed.assert_not_called()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED] is True


@pytest.mark.parametrize(
    "error", [ConnectionLostError("link lost"), OSError("write failed")]
)
async def test_link_drop_during_poll_marks_unavailable(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test a link failure mid-round is an update failure, not an unexpected error."""
    mock_sony_tv.query_volume.side_effect = error

    await _tick(hass, freezer, SCAN_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert _records(caplog, logging.ERROR, "Not connected to the TV") == 1
    assert "Unexpected error" not in caplog.text


async def test_pushed_state_updates_entity(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV
) -> None:
    """Test an acknowledged command's state push reaches the entity."""
    state = default_state()
    state.input_source = InputSource.HDMI2
    state.volume = 50
    state.audio_mute = True
    state.sound_mode = SoundMode.CUSTOM
    mock_sony_tv.mock_state(state)
    await hass.async_block_till_done()

    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_INPUT_SOURCE] == "hdmi2"
    assert attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
    assert attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert attributes[ATTR_SOUND_MODE] == "custom"


async def test_state_unknown_when_nothing_known(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV
) -> None:
    """Test attributes are cleared when the TV reports no state."""
    mock_sony_tv.mock_state(TVState())
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None
    assert state.attributes.get(ATTR_INPUT_SOURCE) is None
    assert state.attributes.get(ATTR_SOUND_MODE) is None


@pytest.mark.parametrize("initial_tv_state", [_standby_state()])
async def test_power_on_push_schedules_refresh(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test an off-to-on transition re-queries the TV once it has booted.

    A second transition before the delay elapses re-arms the timer instead of
    firing twice.
    """
    mock_sony_tv.mock_state(default_state())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    mock_sony_tv.query_power.assert_not_awaited()

    await _tick(hass, freezer, timedelta(seconds=2))
    mock_sony_tv.mock_state(_standby_state())
    mock_sony_tv.mock_state(default_state())
    await hass.async_block_till_done()

    # The first timer would have fired by now; it was cancelled by the re-arm.
    await _tick(hass, freezer, timedelta(seconds=2))
    mock_sony_tv.query_power.assert_not_awaited()

    await _tick(hass, freezer, timedelta(seconds=1))
    mock_sony_tv.query_power.assert_awaited_once()
    mock_sony_tv.query_volume.assert_awaited_once()


@pytest.mark.parametrize("initial_tv_state", [_standby_state()])
async def test_power_on_poll_schedules_refresh(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a power-on found by a poll (the TV's own remote) re-queries it.

    The poll's own attribute queries may land while the set is still booting.
    """
    mock_sony_tv.state.power = PowerState.ON

    await _tick(hass, freezer, SCAN_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    mock_sony_tv.query_power.assert_awaited_once()
    mock_sony_tv.query_volume.assert_awaited_once()

    await _tick(hass, freezer, timedelta(seconds=3))
    assert mock_sony_tv.query_power.await_count == 2
    assert mock_sony_tv.query_volume.await_count == 2

    # Already on: the follow-up poll does not arm another.
    await _tick(hass, freezer, timedelta(seconds=3))
    assert mock_sony_tv.query_power.await_count == 2


@pytest.mark.parametrize("initial_tv_state", [_standby_state()])
async def test_power_on_refresh_cancelled_on_unload(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading the entry cancels a pending power-on refresh."""
    mock_sony_tv.mock_state(default_state())
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _tick(hass, freezer, POWER_ON_REFRESH)
    mock_sony_tv.query_power.assert_not_awaited()


@pytest.mark.parametrize("initial_tv_state", [_standby_state()])
async def test_power_on_refresh_cancelled_on_link_drop(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, freezer: FrozenDateTimeFactory
) -> None:
    """Test a link drop cancels a pending power-on refresh."""
    mock_sony_tv.mock_state(default_state())
    mock_sony_tv.mock_state(None)
    await hass.async_block_till_done()

    await _tick(hass, freezer, POWER_ON_REFRESH)
    mock_sony_tv.query_power.assert_not_awaited()


async def test_power_controls(hass: HomeAssistant, mock_sony_tv: MockSonyTV) -> None:
    """Test power services call the right methods."""
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_sony_tv.power_on.assert_awaited_once()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_sony_tv.power_off.assert_awaited_once()


async def test_volume_controls(hass: HomeAssistant, mock_sony_tv: MockSonyTV) -> None:
    """Test volume state and controls."""
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    assert mock_sony_tv.set_volume.await_args == call(50)

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_sony_tv.volume_up.assert_awaited_once()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_sony_tv.volume_down.assert_awaited_once()


async def test_mute_controls(hass: HomeAssistant, mock_sony_tv: MockSonyTV) -> None:
    """Test mute state and controls."""
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_sony_tv.mute_on.assert_awaited_once()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_sony_tv.mute_off.assert_awaited_once()


async def test_source_and_sound_mode_controls(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV
) -> None:
    """Test source and sound mode state and selection."""
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_INPUT_SOURCE] == "hdmi1"
    assert "hdmi1" in attributes[ATTR_INPUT_SOURCE_LIST]
    assert attributes[ATTR_SOUND_MODE] == "standard"
    assert attributes[ATTR_SOUND_MODE_LIST] == ["dynamic", "standard", "custom"]

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "hdmi3"},
        blocking=True,
    )
    assert mock_sony_tv.select_input_source.await_args == call(InputSource.HDMI3)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "custom"},
        blocking=True,
    )
    assert mock_sony_tv.set_sound_mode.await_args == call(SoundMode.CUSTOM)


@pytest.mark.parametrize(
    ("service", "data", "translation_key"),
    [
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "hdmi9"}, "invalid_source"),
        (
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_SOUND_MODE: "cinema"},
            "invalid_sound_mode",
        ),
    ],
)
async def test_invalid_source_or_sound_mode_raises(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    service: str,
    data: dict[str, str],
    translation_key: str,
) -> None:
    """Test an unknown source or sound mode is rejected before reaching the TV."""
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            MP_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )
    assert excinfo.value.translation_key == translation_key
    mock_sony_tv.select_input_source.assert_not_awaited()
    mock_sony_tv.set_sound_mode.assert_not_awaited()


@pytest.mark.parametrize(
    "exception",
    [
        SonyCommandError(AnswerCode.CANCELED, 0x00),
        CommandTimeoutError("no answer"),
        ConnectionLostError("link dropped"),
        OSError("write failed"),
    ],
)
async def test_command_error_raises(
    hass: HomeAssistant, mock_sony_tv: MockSonyTV, exception: Exception
) -> None:
    """Test library errors raised during an action surface as HomeAssistantError."""
    mock_sony_tv.power_on.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )


def test_translation_keys_cover_all_enum_members() -> None:
    """Test every selectable source and sound mode has a translation key."""
    # TOGGLE is the remote's INPUT key (cycle), not a source to select.
    assert set(INPUT_SOURCE_SONY_TO_HA) == set(InputSource) - {InputSource.TOGGLE}
    assert set(SOUND_MODE_SONY_TO_HA) == set(SoundMode)

    strings = load_json(Path("homeassistant/components/sony_tv_rs232/strings.json"))
    attributes = strings["entity"]["media_player"]["tv"]["state_attributes"]
    assert set(INPUT_SOURCE_SONY_TO_HA.values()) == set(attributes["source"]["state"])
    assert set(SOUND_MODE_SONY_TO_HA.values()) == set(attributes["sound_mode"]["state"])
