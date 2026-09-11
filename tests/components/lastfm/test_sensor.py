"""Tests for the lastfm sensor."""

from pylast import LastFMNetwork, WSError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lastfm.const import (
    ATTR_LAST_PLAYED,
    CONF_API_SECRET,
    CONF_SESSION_KEY,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from homeassistant.core import HomeAssistant

from . import API_KEY, API_SECRET, SESSION_KEY, MockUser
from .conftest import ComponentSetup

from tests.common import MockConfigEntry


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
) -> None:
    """Test sensor stays available when the user hides recent listening info."""
    await setup_integration(config_entry, hidden_user)

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state.state == STATE_NOT_SCROBBLING
    assert state.attributes[ATTR_LAST_PLAYED] is None
    warnings = caplog.text.count("has hidden their recent listening information")
    assert warnings > 0

    await config_entry.runtime_data.async_refresh()

    assert (
        caplog.text.count("has hidden their recent listening information") == warnings
    )


@pytest.mark.parametrize(
    "user",
    [
        pytest.param(
            MockUser(
                thrown_error=WSError(
                    LastFMNetwork(
                        api_key=API_KEY,
                        api_secret=API_SECRET,
                        session_key=SESSION_KEY,
                    ),
                    "status",
                    "Something strange",
                )
            ),
            id="user_data",
        ),
        pytest.param(
            MockUser(
                recent_tracks_error=WSError(
                    LastFMNetwork(
                        api_key=API_KEY,
                        api_secret=API_SECRET,
                        session_key=SESSION_KEY,
                    ),
                    "status",
                    "Something strange",
                )
            ),
            id="recent_tracks",
        ),
    ],
)
async def test_error_log_does_not_include_credentials(
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    user: MockUser,
) -> None:
    """Test authenticated client credentials are excluded from error logs."""
    authenticated_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **config_entry.options,
            CONF_API_SECRET: API_SECRET,
            CONF_SESSION_KEY: SESSION_KEY,
        },
    )

    await setup_integration(authenticated_entry, user)

    assert "Something strange" in caplog.text
    assert API_SECRET not in caplog.text
    assert SESSION_KEY not in caplog.text
