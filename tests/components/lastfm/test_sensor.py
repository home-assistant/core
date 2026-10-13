"""Tests for the lastfm sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pylast import LastFMNetwork, WSError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lastfm.const import (
    ATTR_LAST_PLAYED,
    CONF_API_SECRET,
    CONF_ENABLE_AUTHENTICATION,
    CONF_SESSION_KEY,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import API_KEY, API_SECRET, SESSION_KEY, MockSessionKeyGenerator, MockUser
from .conftest import ComponentSetup

from tests.common import MockConfigEntry, async_fire_time_changed


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


async def test_sensor_now_playing_with_hidden_listening_information(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    hidden_now_playing_user: MockUser,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test now playing stays available when the recent tracks request fails."""
    await setup_integration(config_entry, hidden_now_playing_user)

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state.state == "artist - title"
    assert state.attributes[ATTR_LAST_PLAYED] is None
    warning = (
        "LastFM user testaccount1 has hidden their recent listening information "
        "(https://www.last.fm/settings/privacy)"
    )
    assert warning in caplog.messages

    with patch("pylast.User", return_value=hidden_now_playing_user) as mock_user:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_user.assert_called()
    assert config_entry.runtime_data.last_update_success

    assert caplog.messages.count(warning) == 1


async def test_reconfigure_unlocks_hidden_listening_information(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    hidden_user: MockUser,
    default_user: MockUser,
) -> None:
    """Reload the existing sensor with authenticated access to private tracks."""
    await setup_integration(config_entry, hidden_user)
    entity_id = "sensor.lastfm_testaccount1"
    assert hass.states.get(entity_id).attributes[ATTR_LAST_PLAYED] is None
    original_entity = entity_registry.async_get(entity_id)

    with (
        patch("pylast.User", return_value=default_user),
        patch(
            "homeassistant.components.lastfm.config_flow.SessionKeyGenerator",
            return_value=MockSessionKeyGenerator(),
        ),
        patch("homeassistant.components.lastfm.config_flow.POLLING_INTERVAL", 60),
        patch(
            "homeassistant.components.lastfm.coordinator.LastFMNetwork",
            wraps=LastFMNetwork,
        ) as network,
    ):
        result = await config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: API_KEY,
                CONF_API_SECRET: API_SECRET,
                CONF_ENABLE_AUTHENTICATION: True,
            },
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    network.assert_called_once_with(
        api_key=API_KEY, api_secret=API_SECRET, session_key=SESSION_KEY
    )
    assert hass.states.get(entity_id).attributes[ATTR_LAST_PLAYED] == "artist - title"
    entity = entity_registry.async_get(entity_id)
    assert entity.id == original_entity.id
    assert entity.device_id == original_entity.device_id
    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]


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
    assert API_KEY not in caplog.text
    assert API_SECRET not in caplog.text
    assert SESSION_KEY not in caplog.text
