"""Test Teltonika sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError, ContentTypeError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teltasync import (
    TeltonikaAuthenticationError,
    TeltonikaConnectionError,
    TeltonikaInvalidCredentialsError,
)
from teltasync.error_codes import TeltonikaErrorCode

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor entities match snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_modem_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_modems: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when modem is removed."""

    # Get initial sensor state
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # Update coordinator with empty modem data
    mock_response = MagicMock()
    mock_response.data = []  # No modems
    mock_modems.get_status.return_value = mock_response

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that entity is marked as unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # When modem is removed, entity should be marked as unavailable
    # Verify through entity registry that entity exists but is unavailable
    entity_entry = entity_registry.async_get("sensor.rutx50_test_internal_modem_rssi")
    assert entity_entry is not None
    # State should show unavailable when modem is removed
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_sensor_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable on update failure and recovers."""

    # Get initial sensor state,  here it should be available
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"

    mock_modems.get_status.side_effect = TeltonikaConnectionError("Connection lost")

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"
    # Simulate recovery
    mock_modems.get_status.side_effect = None

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should be available again with correct data
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"


def _has_reauth_flow(hass: HomeAssistant) -> bool:
    """Return whether a reauth flow is in progress for the integration."""
    return bool(
        hass.config_entries.flow.async_progress_by_handler(
            DOMAIN, match_context={"source": SOURCE_REAUTH}
        )
    )


@pytest.mark.parametrize(
    "first_failure",
    [
        TeltonikaAuthenticationError("Session expired"),
        ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
            message="Unauthorized",
            headers=None,
        ),
        ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=403,
            message="Forbidden",
            headers=None,
        ),
        ContentTypeError(
            request_info=MagicMock(),
            history=(),
            status=403,
            message="Attempt to decode JSON with unexpected mimetype: text/html",
            headers=None,
        ),
    ],
    ids=[
        "auth_exception",
        "http_401",
        "http_403",
        "content_type_403",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_dropped_session_recovers_without_reauth(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    mock_teltasync_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    first_failure: Exception,
) -> None:
    """Test a device that drops the session (e.g. on reboot) recovers itself.

    This should not trigger a reauth flow, as the credentials are still valid.
    Instead, the integration should clear the token, re-authenticate, and retry.
    """
    good_response = mock_modems.get_status.return_value
    mock_modems.get_status.side_effect = [first_failure, good_response]

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"

    mock_teltasync_client.auth.authenticate.assert_awaited_once()
    assert _has_reauth_flow(hass) is False


@pytest.mark.parametrize(
    "auth_error",
    [
        TeltonikaInvalidCredentialsError("Invalid username or password"),
        TeltonikaAuthenticationError("Login failed (code 121)"),
    ],
    ids=["invalid_credentials", "login_failed_body_error"],
)
@pytest.mark.usefixtures("init_integration")
async def test_failed_reauthentication_triggers_reauth(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    mock_teltasync_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    auth_error: TeltonikaAuthenticationError,
) -> None:
    """Test a reauth flow starts when re-authentication is rejected.

    Both an HTTP 401 (``TeltonikaInvalidCredentialsError``) and a body error
    code such as LOGIN_FAILED (plain ``TeltonikaAuthenticationError``) mean the
    stored credentials are no longer valid.
    """
    mock_modems.get_status.side_effect = TeltonikaAuthenticationError("Session expired")
    mock_teltasync_client.auth.authenticate.side_effect = auth_error

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    assert _has_reauth_flow(hass) is True


@pytest.mark.usefixtures("init_integration")
async def test_connection_error_during_reauth_is_transient(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    mock_teltasync_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a connection error while re-authenticating does not start a reauth flow."""
    mock_modems.get_status.side_effect = TeltonikaAuthenticationError("Session expired")
    mock_teltasync_client.auth.authenticate.side_effect = TeltonikaConnectionError(
        "Device still rebooting"
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    assert _has_reauth_flow(hass) is False


@pytest.mark.parametrize(
    "side_effect",
    [
        TeltonikaAuthenticationError("Session expired"),
        ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
            message="Unauthorized",
            headers=None,
        ),
        ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Server error",
            headers=None,
        ),
        TeltonikaConnectionError("Connection lost"),
    ],
    ids=["persistent_auth", "http_401", "http_500", "connection_error"],
)
@pytest.mark.usefixtures("init_integration")
async def test_persistent_update_error_marks_unavailable_without_reauth(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test persistent errors mark entities unavailable without a reauth flow."""
    mock_modems.get_status.side_effect = side_effect

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    assert _has_reauth_flow(hass) is False


@pytest.mark.parametrize(
    "error_code",
    [TeltonikaErrorCode.UNAUTHORIZED_ACCESS, 999],
    ids=["api_auth_error", "api_non_auth_error"],
)
@pytest.mark.usefixtures("init_integration")
async def test_unsuccessful_response_marks_unavailable_without_reauth(
    hass: HomeAssistant,
    mock_modems: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error_code: int,
) -> None:
    """Test persistent unsuccessful API responses don't trigger a reauth flow."""
    mock_modems.get_status.side_effect = None
    mock_modems.get_status.return_value = MagicMock(
        success=False,
        data=None,
        errors=[MagicMock(code=error_code, error="API error")],
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"

    assert _has_reauth_flow(hass) is False
