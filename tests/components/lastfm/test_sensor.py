"""Tests for the lastfm sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pylast import LastFMNetwork, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lastfm.const import ATTR_LAST_PLAYED, STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant

from . import API_KEY, MockUser
from .conftest import ComponentSetup


@pytest.mark.parametrize(
    ("fixture"),
    [
        ("not_found_user"),
        ("first_time_user"),
        ("default_user"),
        ("hidden_user"),
        ("recent_tracks_error_user"),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test sensors."""
    user = request.getfixturevalue(fixture)
    await setup_integration(config_entry, user)

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state == snapshot


async def test_sensor_hidden_listening_information(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    hidden_user: MockUser,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor stays available when the user hides recent listening info."""
    await setup_integration(config_entry, hidden_user)

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state.state == STATE_NOT_SCROBBLING
    assert state.attributes[ATTR_LAST_PLAYED] is None
    warnings = caplog.text.count("has hidden their recent listening information")
    assert warnings > 0

    with patch("pylast.User", return_value=hidden_user) as mock_user:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_user.assert_called()
    assert config_entry.runtime_data.last_update_success
    assert (
        caplog.text.count("has hidden their recent listening information") == warnings
    )


@pytest.mark.parametrize(
    "error_kwarg",
    [
        pytest.param("thrown_error", id="user_info"),
        pytest.param("recent_tracks_error", id="recent_tracks"),
    ],
)
async def test_update_error_does_not_log_api_key(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error_kwarg: str,
) -> None:
    """Test the API key in the pylast network repr is not logged."""
    error = WSError(LastFMNetwork(api_key=API_KEY), "8", "Operation failed")
    await setup_integration(config_entry, MockUser(**{error_kwarg: error}))

    assert "LastFM update for testaccount1 failed: Operation failed" in caplog.text
    assert API_KEY not in caplog.text
