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
    CONF_GIID,
    COOKIE_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DRY_RUN_FALLBACK_INTERVAL,
    RATE_LIMIT_BACKOFF,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, update_coordinator

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


@pytest.mark.usefixtures("mock_verisure")
async def test_child_device_links_to_alarm_via_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Child devices link to the alarm (VBox) device via via_device_id."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.verisure.PLATFORMS", [Platform.SWITCH]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    giid = mock_config_entry.data[CONF_GIID]
    alarm_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, giid), mock_config_entry.entry_id
    )
    plug_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "plug-1"), mock_config_entry.entry_id
    )
    assert alarm_device is not None
    assert plug_device is not None
    assert plug_device.via_device_id == alarm_device.id


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


def _overview(door_window_state: str = "CLOSED") -> list:
    """Build a minimal overview payload with a controllable door/window state."""
    return [
        {
            "data": {
                "installation": {
                    "armState": {"status": "DISARMED", "statusType": "DISARMED"},
                    "doorWindows": [
                        {
                            "device": {"deviceLabel": "door-1"},
                            "state": door_window_state,
                        }
                    ],
                }
            }
        }
    ]


DRY_RUN_TRANSACTION = {"data": {"armStateDryRun": "dry-run-txn"}}
DRY_RUN_STATUS_CLEAN = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {"deviceViolations": []},
                }
            }
        }
    }
}
DRY_RUN_STATUS_VIOLATION = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {
                        "deviceViolations": [
                            {
                                "deviceLabel": "door-1",
                                "violation": "DOOR_WINDOW_OPEN",
                            }
                        ]
                    },
                }
            }
        }
    }
}


async def test_force_arm_required_checked_on_first_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """The dry run runs on the first update, since there is no prior fingerprint."""
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
    ]
    await _async_setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is True


async def test_force_arm_required_not_rechecked_when_unchanged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The dry run does not rerun when the door/window state has not changed.

    The mock only provides one overview response for the second update, with no
    dry-run-shaped responses after it; if the coordinator incorrectly reran the
    dry run, the mock would be consumed out of order and this test would fail.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
        _overview("CLOSED"),
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is True

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is True


async def test_force_arm_required_rechecked_when_changed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The dry run reruns as soon as the door/window state changes."""
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
        _overview("OPEN"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is False

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is True


async def test_force_arm_required_rechecked_after_fallback_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The dry run reruns after the fallback interval even if nothing changed.

    This is the safety net for violation types not reflected in door/window
    state, for example an offline or otherwise faulted device.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is True

    freezer.tick(DRY_RUN_FALLBACK_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is False


DRY_RUN_STATUS_INCOMPLETE = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {},
                }
            }
        }
    }
}


async def test_force_arm_required_rate_limit_defers_next_check(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rate limit during the periodic fallback check defers the next attempt.

    The door/window state never changes here, so a rechecked dry run only
    happens because the fallback interval elapsed. The mock only provides one
    overview response for the third update, with no dry-run-shaped responses
    after it; if the coordinator retried the dry run right away instead of
    backing off, the mock would be consumed out of order and this test would
    fail. The rate limit also clears the previously known readiness, since a
    failed recheck no longer confirms the earlier answer still holds.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
        _overview("CLOSED"),
        RateLimitError("AUT_00021"),
        _overview("CLOSED"),
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is False

    freezer.tick(DRY_RUN_FALLBACK_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.data["force_arm_required"] is None

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is None


async def test_force_arm_required_rate_limit_defers_changed_fingerprint_recheck(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rate limit also defers a recheck triggered by a changed fingerprint.

    The fingerprint is only stored on success, so after the rate limit the
    door/window state still looks "changed" on the next cycle too. The mock
    only provides an overview response for that cycle, with no dry-run-shaped
    responses after it; if the coordinator retried just because the
    fingerprint still looked changed, instead of honoring the backoff
    deadline, the mock would be consumed out of order and this test would
    fail.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
        _overview("OPEN"),
        RateLimitError("AUT_00021"),
        _overview("OPEN"),
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is False

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.data["force_arm_required"] is None

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is None


DRY_RUN_STATUS_PENDING = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "PENDING"},
                }
            }
        }
    }
}


async def test_force_arm_required_defers_after_exhausting_poll_attempts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A dry run that never reaches DONE backs off instead of retrying immediately.

    Without a deferred retry, a transaction that never completes would start
    a brand new one on every one-minute cycle, indefinitely. The mock only
    provides one overview response for the second update, with no
    dry-run-shaped responses after it; if the coordinator started another
    dry run right away instead of backing off, the mock would be consumed
    out of order and this test would fail.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        *([DRY_RUN_STATUS_PENDING] * 30),
        _overview("CLOSED"),
    ]
    with patch("homeassistant.components.verisure.coordinator.asyncio.sleep"):
        await _async_setup(hass, mock_config_entry)
        coordinator = mock_config_entry.runtime_data
        assert coordinator.data["force_arm_required"] is None

        freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is None


async def test_force_arm_required_ignores_incomplete_dry_run_result(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """A DONE dry run without a violations list is not treated as ready.

    The result dict is missing "deviceViolations" entirely; treating that as
    an empty list would incorrectly report the alarm as ready to arm.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_INCOMPLETE,
    ]
    await _async_setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is None


DRY_RUN_STATUS_NULL_VIOLATIONS = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {"deviceViolations": None},
                }
            }
        }
    }
}


async def test_force_arm_required_ignores_null_device_violations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """A DONE dry run with deviceViolations set to null is not treated as ready.

    The key is present but its value is not a list; bool(None) is False,
    which would incorrectly report the alarm as ready to arm.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_NULL_VIOLATIONS,
    ]
    await _async_setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is None


DRY_RUN_START_NULL_DATA = {"data": None}


async def test_force_arm_required_ignores_null_data_starting_dry_run(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """A GraphQL error response with data set to null does not crash setup.

    vsure.request() can return an HTTP-200 GraphQL error payload with "data"
    explicitly null rather than missing. dict.get("data", {}) only falls
    back to {} when the key is absent, not when its value is null, so a
    naive chained .get() would raise AttributeError instead of leaving
    readiness unknown.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_START_NULL_DATA,
    ]
    await _async_setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is None


DRY_RUN_STATUS_NULL_DRY_RUN_STATUS = {
    "data": {"installation": {"armState": {"dryRunStatus": None}}}
}


async def test_force_arm_required_ignores_null_dry_run_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """A poll response with dryRunStatus set to null does not crash setup."""
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_NULL_DRY_RUN_STATUS,
    ]
    await _async_setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is None


async def test_force_arm_required_failure_retried_next_cycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed dry run does not break the update and is retried next cycle.

    The door/window state is unchanged between cycles; the retry happens
    because a failed attempt does not update the stored fingerprint.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        RequestError("offline"),
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is None
    assert hass.states.get(ALARM_ENTITY_ID).state == "disarmed"

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is True


async def test_force_arm_required_retries_after_failure_even_if_fingerprint_reverts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry is still due if the door/window state reverts after a failure.

    The fingerprint is only stored on success, so once the door closes again
    it matches the earlier CLOSED baseline from before the failed OPEN check.
    Without also gating on the last known readiness, that coincidental match
    would look like nothing changed and silently skip the promised retry.
    """
    mock_verisure.request.side_effect = [
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
        _overview("OPEN"),
        RequestError("offline"),
        _overview("CLOSED"),
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
    ]
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["force_arm_required"] is False

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.data["force_arm_required"] is None

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["force_arm_required"] is True
