"""Test squeezebox sensors."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.squeezebox.const import PLAYER_UPDATE_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from .conftest import FAKE_QUERY_RESPONSE, TEST_ALARM_NEXT_TIME

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def squeezebox_sensor_platform():
    """Only set up the sensor platform for these tests."""
    with patch("homeassistant.components.squeezebox.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_server_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that server sensor reports correct player count."""

    # Setup component
    with patch(
        "homeassistant.components.squeezebox.Server.async_query",
        return_value=deepcopy(FAKE_QUERY_RESPONSE),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.fakelib_player_count")

    assert state is not None
    assert state.state == "10"


async def test_player_sensor_next_alarm(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test player sensor for time of next alarm."""

    # Setup component
    lms.async_prepared_status.return_value = {
        "dummy": False,
    }
    with patch("homeassistant.components.squeezebox.Server", return_value=lms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    player = (await lms.async_get_players())[0]

    # test alarm time is set from player
    state = hass.states.get("sensor.next_alarm")
    assert state is not None
    assert state.state == TEST_ALARM_NEXT_TIME.isoformat()

    # simulate no upcoming alarm
    player.alarm_next = None
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.next_alarm")
    assert state is not None
    assert state.state == STATE_UNKNOWN
