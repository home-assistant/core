"""Test squeezebox binary sensors."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.squeezebox.const import PLAYER_UPDATE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .conftest import FAKE_QUERY_RESPONSE

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def squeezebox_binary_sensor_platform():
    """Only set up the binary_sensor platform for squeezebox tests."""
    with patch(
        "homeassistant.components.squeezebox.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


async def test_binary_server_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""
    with patch(
        "homeassistant.components.squeezebox.Server.async_query",
        return_value=deepcopy(FAKE_QUERY_RESPONSE),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.fakelib_needs_restart")

    assert state is not None
    assert state.state == STATE_OFF


@pytest.fixture
async def mock_player(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
) -> MagicMock:
    """Set up the squeezebox integration and return the mocked player."""

    # Mock server status data for coordinator update
    # called on update, return something != None to not raise
    lms.async_prepared_status.return_value = {
        "dummy": False,
    }
    with patch("homeassistant.components.squeezebox.Server", return_value=lms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Return the player mock
    return (await lms.async_get_players())[0]


async def test_player_alarm_sensors_state(
    hass: HomeAssistant,
    mock_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test player alarm binary sensors with default states."""

    player = mock_player

    # Test alarm upcoming sensor
    upcoming_state = hass.states.get("binary_sensor.none_alarm_upcoming")
    assert upcoming_state is not None
    assert upcoming_state.state == STATE_ON

    # Test alarm active sensor
    active_state = hass.states.get("binary_sensor.none_alarm_active")
    assert active_state is not None
    assert active_state.state == STATE_OFF

    # Test alarm snooze sensor
    snooze_state = hass.states.get("binary_sensor.none_alarm_snoozed")
    assert snooze_state is not None
    assert snooze_state.state == STATE_OFF

    # Toggle alarm states and verify sensors update
    player.alarm_upcoming = False
    player.alarm_active = True
    player.alarm_snooze = True
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    upcoming_state = hass.states.get("binary_sensor.none_alarm_upcoming")
    assert upcoming_state is not None
    assert upcoming_state.state == STATE_OFF

    active_state = hass.states.get("binary_sensor.none_alarm_active")
    assert active_state is not None
    assert active_state.state == STATE_ON

    snooze_state = hass.states.get("binary_sensor.none_alarm_snoozed")
    assert snooze_state is not None
    assert snooze_state.state == STATE_ON
