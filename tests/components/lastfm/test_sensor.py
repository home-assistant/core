"""Tests for the lastfm sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pylast import (
    LastFMNetwork,
    MalformedResponseError,
    NetworkError,
    PyLastError,
    Track,
    WSError,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lastfm.const import (
    ATTR_LAST_PLAYED,
    CONF_API_SECRET,
    CONF_ENABLE_AUTHENTICATION,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    CONF_API_KEY,
    MAX_LENGTH_STATE_STATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import API_KEY, API_SECRET, COVER_IMAGE, SESSION_KEY, MockNetwork, MockUser
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


async def test_sensor_without_avatar(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    no_cover_user: MockUser,
) -> None:
    """Test a user without an avatar or album art has no entity picture."""
    with patch.object(no_cover_user, "get_image", return_value=None):
        await setup_integration(config_entry, no_cover_user)

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state.state == "artist - title"
    assert ATTR_ENTITY_PICTURE not in state.attributes


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


@pytest.mark.usefixtures("mock_session_key_generator")
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
    "error_kwarg",
    [
        pytest.param("thrown_error", id="user_info"),
        pytest.param("recent_tracks_error", id="recent_tracks"),
    ],
)
@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(
            WSError(
                LastFMNetwork(
                    api_key=API_KEY,
                    api_secret=API_SECRET,
                    session_key=SESSION_KEY,
                ),
                "8",
                "Operation failed",
            ),
            "8: Operation failed",
            id="api_error",
        ),
        pytest.param(
            PyLastError("Something strange"),
            "Something strange",
            id="library_error",
        ),
    ],
)
async def test_error_log_does_not_include_credentials(
    setup_integration: ComponentSetup,
    authenticated_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error_kwarg: str,
    error: PyLastError,
    message: str,
) -> None:
    """Test API and library error logs exclude authenticated client credentials."""
    await setup_integration(
        authenticated_config_entry, MockUser(**{error_kwarg: error})
    )

    assert f"LastFM update for testaccount1 failed: {message}" in caplog.text
    assert API_KEY not in caplog.text
    assert API_SECRET not in caplog.text
    assert SESSION_KEY not in caplog.text


async def test_all_entities(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    await setup_integration(config_entry, default_user)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("fixture", "entity_id", "picture"),
    [
        pytest.param(
            "default_user", "sensor.lastfm_testaccount1", COVER_IMAGE, id="playing"
        ),
        pytest.param(
            "first_time_user", "sensor.lastfm_testaccount1", "image", id="not_playing"
        ),
        pytest.param(
            "no_cover_user", "sensor.lastfm_testaccount1", "image", id="no_cover"
        ),
        pytest.param(
            "default_user",
            "sensor.lastfm_testaccount1_last_played",
            COVER_IMAGE,
            id="last_played",
        ),
        pytest.param(
            "no_cover_user",
            "sensor.lastfm_testaccount1_last_played",
            None,
            id="last_played_no_cover",
        ),
        pytest.param(
            "default_user",
            "sensor.lastfm_testaccount1_top_track",
            COVER_IMAGE,
            id="top_track",
        ),
    ],
)
async def test_entity_picture(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    fixture: str,
    entity_id: str,
    picture: str | None,
    request: pytest.FixtureRequest,
) -> None:
    """Test the album art is used as entity picture."""
    await setup_integration(config_entry, request.getfixturevalue(fixture))

    assert hass.states.get(entity_id).attributes.get(ATTR_ENTITY_PICTURE) == picture


async def test_cover_image_requested_once(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the album art is only requested when the track changes."""
    with patch.object(
        Track, "get_cover_image", autospec=True, return_value=COVER_IMAGE
    ) as mock_cover:
        await setup_integration(config_entry, default_user)
        assert mock_cover.call_count == 1

        with patch("pylast.User", return_value=default_user):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_cover.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NetworkError("network", OSError()), id="network_error"),
        pytest.param(
            MalformedResponseError("network", ValueError()), id="malformed_response"
        ),
        pytest.param(
            WSError("network", "11", "Service Offline"), id="retryable_api_error"
        ),
    ],
)
async def test_cover_image_transient_error_retried(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
    error: PyLastError,
) -> None:
    """Test a failed album art request is retried on the next update only."""
    entity_id = "sensor.lastfm_testaccount1_top_track"
    with patch.object(
        Track, "get_cover_image", autospec=True, side_effect=error
    ) as mock_cover:
        await setup_integration(config_entry, default_user)
        # The same track is playing, last played and top track
        assert mock_cover.call_count == 1
        assert hass.states.get(entity_id).attributes.get(ATTR_ENTITY_PICTURE) is None

        mock_cover.side_effect = None
        mock_cover.return_value = COVER_IMAGE
        with patch("pylast.User", return_value=default_user):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_cover.call_count == 2
    assert hass.states.get(entity_id).attributes[ATTR_ENTITY_PICTURE] == COVER_IMAGE


async def test_cover_image_permanent_error_cached(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the album art is not requested again after a permanent error."""
    with patch.object(
        Track,
        "get_cover_image",
        autospec=True,
        side_effect=WSError("network", "6", "Track not found"),
    ) as mock_cover:
        await setup_integration(config_entry, default_user)

        with patch("pylast.User", return_value=default_user):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_cover.call_count == 1
    assert (
        hass.states.get("sensor.lastfm_testaccount1_top_track").attributes.get(
            ATTR_ENTITY_PICTURE
        )
        is None
    )


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.lastfm_testaccount1_last_played",
        "sensor.lastfm_testaccount1_top_track",
    ],
)
async def test_long_track_state_truncated(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test track states longer than the state limit are truncated."""
    track = Track(
        "artist",
        "t" * MAX_LENGTH_STATE_STATE,
        MockNetwork("lastfm"),
        info={"image": []},
    )
    await setup_integration(config_entry, MockUser(recent_tracks=[track]))

    state = hass.states.get(entity_id).state
    assert state == f"artist - {'t' * MAX_LENGTH_STATE_STATE}"[:MAX_LENGTH_STATE_STATE]
