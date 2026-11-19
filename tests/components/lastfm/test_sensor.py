"""Tests for the lastfm sensor."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pylast import LastFMNetwork, PyLastError, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lastfm.const import (
    ATTR_ALBUM,
    ATTR_ARTIST,
    ATTR_LAST_PLAYED,
    ATTR_TIMESTAMP,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_SCROBBLE,
    STATE_NOT_SCROBBLING,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import API_KEY, MockUser
from .conftest import ComponentSetup

SENSOR = "sensor.lastfm_testaccount1"
SCROBBLE_DATA = {ATTR_ARTIST: "Queen", ATTR_TITLE: "Bohemian Rhapsody"}


@pytest.fixture(name="scrobble")
def mock_scrobble() -> Generator[MagicMock]:
    """Patch the scrobble call of pylast, checking the call signature."""
    with patch.object(LastFMNetwork, "scrobble", autospec=True) as mock:
        yield mock


async def test_scrobble_action(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    scrobble_config_entry: MockConfigEntry,
    default_user: MockUser,
    scrobble: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test scrobbling with the credentials of the targeted user."""
    freezer.move_to("2026-11-19 12:00:00+00:00")
    await hass.config.async_set_time_zone("UTC")
    await setup_integration(scrobble_config_entry, default_user)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SCROBBLE,
        {
            ATTR_ENTITY_ID: SENSOR,
            **SCROBBLE_DATA,
            ATTR_ALBUM: "A Night at the Opera",
        },
        blocking=True,
    )

    scrobble.assert_called_once()
    network = scrobble.call_args.args[0]
    assert network.session_key == "oldkey1"
    assert scrobble.call_args.kwargs == {
        "artist": "Queen",
        "title": "Bohemian Rhapsody",
        "timestamp": int(datetime(2026, 11, 19, 12, 0, tzinfo=UTC).timestamp()),
        "album": "A Night at the Opera",
    }


@pytest.mark.parametrize(
    ("time_zone", "timestamp", "expected"),
    [
        ("UTC", None, datetime(2026, 11, 19, 12, 0, tzinfo=UTC)),
        (
            "Europe/Stockholm",
            "2026-11-18 12:00:00",
            datetime(2026, 11, 18, 11, 0, tzinfo=UTC),
        ),
    ],
    ids=["default_now", "naive_local_time"],
)
async def test_scrobble_action_timestamp(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    scrobble_config_entry: MockConfigEntry,
    default_user: MockUser,
    scrobble: MagicMock,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
    timestamp: str | None,
    expected: datetime,
) -> None:
    """Test the timestamp default and its time zone handling."""
    freezer.move_to("2026-11-19 12:00:00+00:00")
    await hass.config.async_set_time_zone(time_zone)
    await setup_integration(scrobble_config_entry, default_user)

    data = {ATTR_ENTITY_ID: SENSOR, **SCROBBLE_DATA}
    if timestamp:
        data[ATTR_TIMESTAMP] = timestamp
    await hass.services.async_call(DOMAIN, SERVICE_SCROBBLE, data, blocking=True)

    assert scrobble.call_args.kwargs["timestamp"] == int(expected.timestamp())


@pytest.mark.parametrize(
    "timestamp",
    ["2026-11-19 13:00:00", "2026-11-04 11:00:00"],
    ids=["future", "too_old"],
)
async def test_scrobble_action_timestamp_out_of_range(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    scrobble_config_entry: MockConfigEntry,
    default_user: MockUser,
    scrobble: MagicMock,
    freezer: FrozenDateTimeFactory,
    timestamp: str,
) -> None:
    """Test timestamps in the future or older than 14 days are rejected."""
    freezer.move_to("2026-11-19 12:00:00+00:00")
    await hass.config.async_set_time_zone("UTC")
    await setup_integration(scrobble_config_entry, default_user)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCROBBLE,
            {ATTR_ENTITY_ID: SENSOR, **SCROBBLE_DATA, ATTR_TIMESTAMP: timestamp},
            blocking=True,
        )

    assert exc_info.value.translation_key == "timestamp_out_of_range"
    scrobble.assert_not_called()


async def test_scrobble_action_user_not_authorized(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    scrobble: MagicMock,
) -> None:
    """Test scrobbling for a user without a session key."""
    await setup_integration(config_entry, default_user)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCROBBLE,
            {ATTR_ENTITY_ID: SENSOR, **SCROBBLE_DATA},
            blocking=True,
        )

    assert exc_info.value.translation_key == "user_not_authorized"
    assert exc_info.value.translation_placeholders == {"username": "testaccount1"}
    scrobble.assert_not_called()


async def test_scrobble_action_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    scrobble_config_entry: MockConfigEntry,
    default_user: MockUser,
    scrobble: MagicMock,
) -> None:
    """Test a pylast error becomes a translated action error."""
    await setup_integration(scrobble_config_entry, default_user)
    error = PyLastError("network", "status", "Operation failed")
    scrobble.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCROBBLE,
            {ATTR_ENTITY_ID: SENSOR, **SCROBBLE_DATA},
            blocking=True,
        )

    assert exc_info.value.translation_key == "scrobble_failed"
    assert exc_info.value.__cause__ is error


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
