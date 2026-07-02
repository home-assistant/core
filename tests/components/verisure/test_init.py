"""Tests for Verisure integration setup and session handling."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from verisure import (
    AuthenticationError,
    CookieReadError,
    Error as VerisureBaseError,
    LoginError,
    RateLimitError,
    RequestError,
    ResponseError,
)

from homeassistant.components.verisure.const import (
    COOKIE_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RATE_LIMIT_BACKOFF,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from tests.common import MockConfigEntry, async_fire_time_changed

ALARM_ENTITY_ID = "alarm_control_panel.verisure_alarm"


async def _async_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the Verisure integration."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.verisure.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _async_trigger_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    *,
    expire_cookie: bool = True,
) -> None:
    """Advance time to trigger a scheduled coordinator refresh."""
    if expire_cookie:
        freezer.tick(COOKIE_REFRESH_INTERVAL)
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_setup_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Test successful setup loads the config entry."""
    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called_once()
    mock_verisure.set_giid.assert_called_once()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"


@pytest.mark.parametrize(
    "exc",
    [
        RequestError("network"),
        ResponseError(503, "server error"),
        RateLimitError("rate limited"),
    ],
)
async def test_setup_transient_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    exc: Exception,
) -> None:
    """Transient failures during login put the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = exc

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_verisure.set_giid.assert_not_called()


async def test_setup_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Invalid credentials during login put the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = AuthenticationError(
        "auth failed", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_setup_cookie_read_uses_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Unreadable cookie file falls back to password login during setup."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()
    mock_verisure.set_giid.assert_called_once()


async def test_setup_cookie_read_transient_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Transient password login after cookie read puts the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = RequestError("offline")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_verisure.set_giid.assert_not_called()


async def test_setup_cookie_read_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Authentication failure after cookie read puts the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cookie_read_mfa_required_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """MFA-only accounts trigger reauth when password login is required."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = LoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_setup_unexpected_verisure_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Unexpected Verisure errors during login put the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = VerisureBaseError("unknown")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_login_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """LoginError during setup puts the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = LoginError("login failed")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exc",
    [
        RequestError("offline"),
        ResponseError(503, "server error"),
        RateLimitError("rate limited"),
    ],
)
async def test_setup_transient_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    exc: Exception,
) -> None:
    """Transient failures during the first refresh put the entry in SETUP_RETRY."""
    mock_verisure.update_cookie.side_effect = exc

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_authentication_error_recovers_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Expired session cookie during first refresh is recovered via login_cookie."""
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"


async def test_setup_cookie_read_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Corrupt cookie during first refresh re-authenticates with password."""
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()


async def test_setup_login_error_recovers_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Recoverable LoginError during first refresh triggers session recovery."""
    mock_verisure.update_cookie.side_effect = LoginError("token refresh failed")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_verisure.login_cookie.call_count >= 2


async def test_setup_overview_request_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Failures while fetching overview put the entry in SETUP_RETRY."""
    mock_verisure.request.side_effect = RequestError("offline")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_authentication_error_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Expired session during update is recovered without triggering reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login_cookie.reset_mock()
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called_once()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_update_authentication_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Authentication failure during session refresh triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = AuthenticationError(
        "invalid session", status_code=403
    )

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_cookie_read_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Corrupt cookie during update re-authenticates with password."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login.reset_mock()
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"


async def test_update_cookie_read_password_login_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Transient failure during cookie-read password login marks entity unavailable."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = RequestError("offline")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ALARM_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_update_cookie_read_password_login_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Authentication failure after cookie-read password login triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_transient_update_cookie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Transient failures during cookie refresh mark the entity unavailable."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = RequestError("offline")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ALARM_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_update_rate_limit_cookie_refresh_backoff(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Rate limits during cookie refresh defer the next poll."""
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_verisure.update_cookie.side_effect = RateLimitError("AUT_00021")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is False
    assert hass.states.get(ALARM_ENTITY_ID).state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, update_coordinator.UpdateFailed)
    assert (
        coordinator.last_exception.retry_after == RATE_LIMIT_BACKOFF[0].total_seconds()
    )


async def test_update_rate_limit_backoff_escalates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Repeated rate limits increase the backoff delay."""
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_verisure.update_cookie.side_effect = RateLimitError("AUT_00021")

    await _async_trigger_coordinator_update(hass, freezer)
    assert (
        coordinator.last_exception.retry_after == RATE_LIMIT_BACKOFF[0].total_seconds()
    )

    freezer.tick(RATE_LIMIT_BACKOFF[0] + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        coordinator.last_exception.retry_after == RATE_LIMIT_BACKOFF[1].total_seconds()
    )


async def test_update_rate_limit_backoff_resets_on_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Successful updates reset rate-limit backoff."""
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_verisure.update_cookie.side_effect = RateLimitError("AUT_00021")

    await _async_trigger_coordinator_update(hass, freezer)
    assert coordinator._rate_limit_backoff_level == 1

    mock_verisure.update_cookie.side_effect = None
    freezer.tick(RATE_LIMIT_BACKOFF[0] + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator._rate_limit_backoff_level == 0
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"


async def test_update_skips_cookie_refresh_when_recent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Cookie refresh is skipped when the session cookie is still fresh."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.reset_mock()

    await _async_trigger_coordinator_update(hass, freezer, expire_cookie=False)

    mock_verisure.update_cookie.assert_not_called()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"

    await _async_trigger_coordinator_update(hass, freezer)

    mock_verisure.update_cookie.assert_called_once()


async def test_update_session_refresh_cookie_read_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Cookie read during session refresh falls back to password login."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login.reset_mock()
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"


async def test_update_session_refresh_login_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """LoginError during session refresh triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = LoginError("login failed")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_session_refresh_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Transient errors during session refresh mark the entity unavailable."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = ResponseError(503, "server error")

    await _async_trigger_coordinator_update(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ALARM_ENTITY_ID).state == STATE_UNAVAILABLE
