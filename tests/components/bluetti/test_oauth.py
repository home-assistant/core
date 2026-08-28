"""Tests for oauth.py: OAuth2FlowHandler helpers and AuthTokenRefresh."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock, patch

from pybluetti import UserProduct

from homeassistant.components.bluetti import _async_update_listener
from homeassistant.components.bluetti.config_flow import BluettiConfigFlow
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.oauth import (
    ISSUE_ID_OAUTH_EXPIRED,
    AsyncConfigEntryAuth,
    AuthTokenRefresh,
    OAuth2FlowHandler,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


def _refresher(
    hass: HomeAssistant, token: dict
) -> tuple[AuthTokenRefresh, MockConfigEntry]:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = token
    return AuthTokenRefresh(hass, entry, session), entry


def test_logger_property() -> None:
    """Logger property."""
    flow = OAuth2FlowHandler()
    assert flow.logger.name == "homeassistant.components.bluetti.oauth"


async def test_async_oauth_create_entry_delegates_to_select_devices(
    hass: HomeAssistant,
) -> None:
    """Async oauth create entry delegates to select devices."""
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.async_step_select_devices = AsyncMock(
        return_value={"type": "abort", "reason": "success"}
    )

    result = await flow.async_oauth_create_entry({"token": {"access_token": "x"}})

    assert flow._oauth_data == {"token": {"access_token": "x"}}
    flow.async_step_select_devices.assert_awaited_once_with()
    assert result["reason"] == "success"


async def test_async_step_reconfigure_missing_entry_aborts(hass: HomeAssistant) -> None:
    """Async step reconfigure missing entry aborts."""
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"entry_id": "does-not-exist"}

    result = await flow.async_step_reconfigure()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"


async def test_async_step_reconfigure_delegates_to_async_step_user(
    hass: HomeAssistant,
) -> None:
    """Async step reconfigure delegates to async step user."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}
    flow.async_step_user = AsyncMock(return_value={"type": "form"})

    result = await flow.async_step_reconfigure()

    assert flow.entry.entry_id == entry.entry_id
    flow.async_step_user.assert_awaited_once()
    assert result["type"] == "form"


async def test_token_refresh_init_subscribes_and_unsubs_on_unload(
    hass: HomeAssistant,
) -> None:
    """The onTokenExpired listener must actually fire, then stop after unload.

    Regression test: this test used to only fire the event and call
    async_block_till_done() with no assertion at all - it would still
    pass even if entry.async_on_unload(unsub) were never called, since
    nothing here ever checked the listener was subscribed, let alone
    unsubscribed.
    """
    refresher, entry = _refresher(hass, {})
    assert refresher.entry is entry
    refresher.send_expired_notification = MagicMock()

    hass.bus.async_fire("onTokenExpired")
    await hass.async_block_till_done()
    refresher.send_expired_notification.assert_called_once()

    await entry._async_process_on_unload(hass)

    refresher.send_expired_notification.reset_mock()
    hass.bus.async_fire("onTokenExpired")
    await hass.async_block_till_done()
    refresher.send_expired_notification.assert_not_called()


async def test_on_token_expired_event_sends_notification(hass: HomeAssistant) -> None:
    """On token expired event sends notification."""
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.on_token_expired_event(None)

    refresher.send_expired_notification.assert_called_once()


def test_is_token_valid_no_token(hass: HomeAssistant) -> None:
    """Is token valid no token."""
    refresher, _entry = _refresher(hass, {})
    assert refresher.is_token_valid() is False


def test_is_token_valid_expires_at_in_future(hass: HomeAssistant) -> None:
    """Is token valid expires at in future."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    assert refresher.is_token_valid() is True


def test_is_token_valid_expires_at_in_past(hass: HomeAssistant) -> None:
    """Is token valid expires at in past."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() - 1000})
    assert refresher.is_token_valid() is False


def test_is_token_valid_expires_in_created_at_future(hass: HomeAssistant) -> None:
    """Is token valid expires in created at future."""
    refresher, _entry = _refresher(
        hass, {"created_at": time.time(), "expires_in": 1000}
    )
    assert refresher.is_token_valid() is True


def test_is_token_valid_expires_in_created_at_past(hass: HomeAssistant) -> None:
    """Is token valid expires in created at past."""
    refresher, _entry = _refresher(
        hass, {"created_at": time.time() - 5000, "expires_in": 100}
    )
    assert refresher.is_token_valid() is False


def test_is_token_valid_no_recognizable_fields(hass: HomeAssistant) -> None:
    """Is token valid no recognizable fields."""
    refresher, _entry = _refresher(hass, {"some_other_field": True})
    assert refresher.is_token_valid() is False


async def test_start_token_check_invalid_token_sends_notification(
    hass: HomeAssistant,
) -> None:
    """Start token check invalid token sends notification."""
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()
    refresher.async_check_token_expiry = AsyncMock()

    refresher.start_token_check()
    await hass.async_block_till_done()

    refresher.send_expired_notification.assert_called_once()
    refresher.async_check_token_expiry.assert_awaited_once()


async def test_start_token_check_valid_token_runs_the_check_once(
    hass: HomeAssistant,
) -> None:
    """Start token check valid token runs the check once."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    refresher.send_expired_notification = MagicMock()
    refresher.async_check_token_expiry = AsyncMock()

    refresher.start_token_check()
    await hass.async_block_till_done()

    refresher.send_expired_notification.assert_not_called()
    refresher.async_check_token_expiry.assert_awaited_once()


def test_send_expired_notification_creates_notification(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Send expired notification creates notification."""
    refresher, _entry = _refresher(hass, {})

    with patch(
        "homeassistant.components.bluetti.oauth.persistent_notification.async_create"
    ) as mock_create:
        refresher.send_expired_notification()

    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["notification_id"] == "notifyTokenExpire"

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID_OAUTH_EXPIRED)
    assert issue is not None
    assert issue.translation_key == "oauth_expired"
    assert issue.is_fixable is False


async def test_start_token_check_clears_issue_when_token_becomes_valid(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Start token check clears issue when token becomes valid."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    refresher.async_check_token_expiry = AsyncMock()
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID_OAUTH_EXPIRED,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="oauth_expired",
    )

    refresher.start_token_check()
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID_OAUTH_EXPIRED) is None


async def test_async_check_token_expiry_accepts_the_timer_callback_signature(
    hass: HomeAssistant,
) -> None:
    """async_track_time_interval always invokes its callback with a datetime.

    Regression test: this method is registered directly as that callback in
    start_token_check - if it didn't accept a positional `now`, every timer
    fire would raise TypeError and silently break the daily proactive check.
    """
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry(dt_util.naive_now())

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_no_expires_at_logs_and_returns(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry no expires at logs and returns."""
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_already_expired(hass: HomeAssistant) -> None:
    """Async check token expiry already expired."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() - 10})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_called_once()


async def test_async_check_token_expiry_refreshes_an_already_expired_token(
    hass: HomeAssistant,
) -> None:
    """An already-expired access token must still be refreshed, not just reported.

    Regression test: the already-expired branch used to notify immediately
    without ever attempting a refresh - an access token past its own
    (often much shorter) expiry is exactly the normal case a refresh token
    exists for, not necessarily a real problem. A daily periodic check
    landing after that point used to show a false "expired" warning every
    time even though a refresh would have quietly succeeded.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    entry.add_update_listener(_async_update_listener)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 10}
    session.implementation.async_refresh_token = AsyncMock(
        return_value={"access_token": "new"}
    )
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await refresher.async_check_token_expiry()
        await hass.async_block_till_done()

    session.implementation.async_refresh_token.assert_awaited_once()
    mock_reload.assert_awaited_once_with(entry.entry_id)
    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_not_due_soon_does_nothing(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry not due soon does nothing."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 3600 * 24 * 30})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_recent_refresh_is_skipped(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry recent refresh is skipped."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"last_token_refresh": time.time() - 60}
    )
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    refresher = AuthTokenRefresh(hass, entry, session)

    await refresher.async_check_token_expiry()

    session.implementation.async_refresh_token.assert_not_called()


async def test_async_check_token_expiry_notifies_when_rate_limited_and_expired(
    hass: HomeAssistant,
) -> None:
    """A recently-refreshed but already-expired token still notifies."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"last_token_refresh": time.time() - 60}
    )
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    session.implementation.async_refresh_token.assert_not_called()
    refresher.send_expired_notification.assert_called_once()


async def test_async_check_token_expiry_refreshes_and_reloads(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry refreshes and reloads exactly once.

    Regression test: async_check_token_expiry() used to call
    hass.config_entries.async_reload() explicitly right after
    async_update_entry() - on a loaded entry (mock_reload here, matching a
    real one via the update listener registered below), that update
    already fires the entry's registered update listener, which reloads
    it - the explicit call fired a second, redundant reload.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    entry.add_update_listener(_async_update_listener)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    session.implementation.async_refresh_token = AsyncMock(
        return_value={"access_token": "new"}
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await refresher.async_check_token_expiry()
        await hass.async_block_till_done()

    session.implementation.async_refresh_token.assert_awaited_once()
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data["token"] == {"access_token": "new"}
    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_async_check_token_expiry_starts_reauth_on_invalid_refresh_token(
    hass: HomeAssistant,
) -> None:
    """A revoked/invalid refresh token must start the standard reauth flow.

    Regression test: calling the implementation directly (rather than
    going through OAuth2Session.async_ensure_token_valid(), which handles
    this itself) meant nothing started reauth when the refresh token was
    no longer valid - an entry with no device coordinator has no other
    request that would.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            domain=DOMAIN, request_info=MagicMock()
        )
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth:
        await refresher.async_check_token_expiry()

    mock_start_reauth.assert_called_once_with(hass)


async def test_async_check_token_expiry_notifies_and_starts_reauth_when_already_expired(
    hass: HomeAssistant,
) -> None:
    """An already-expired token with an invalid refresh token does both."""
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 10}
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            domain=DOMAIN, request_info=MagicMock()
        )
    )
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    with patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth:
        await refresher.async_check_token_expiry()

    mock_start_reauth.assert_called_once_with(hass)
    refresher.send_expired_notification.assert_called_once()


async def test_schedule_next_check_halves_remaining_time(hass: HomeAssistant) -> None:
    """The next check is scheduled at half the remaining time, not fixed.

    Regression test: a fixed daily interval reached a short-lived token
    too late - it could already be expired by the time the next check ran.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 3600 * 4}  # 4 hours left
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch(
        "homeassistant.components.bluetti.oauth.async_track_point_in_time"
    ) as mock_track:
        refresher._schedule_next_check()

    mock_track.assert_called_once()
    scheduled_at = mock_track.call_args.args[2]
    delay = scheduled_at - dt_util.utcnow()
    assert timedelta(hours=1, minutes=55) < delay < timedelta(hours=2, minutes=5)


async def test_schedule_next_check_caps_at_one_day(hass: HomeAssistant) -> None:
    """A long-lived token is still checked at most once a day."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 3600 * 24 * 30}  # 30 days left
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch(
        "homeassistant.components.bluetti.oauth.async_track_point_in_time"
    ) as mock_track:
        refresher._schedule_next_check()

    scheduled_at = mock_track.call_args.args[2]
    delay = scheduled_at - dt_util.utcnow()
    assert timedelta(hours=23, minutes=55) < delay < timedelta(days=1, minutes=5)


async def test_schedule_next_check_floors_at_five_minutes(hass: HomeAssistant) -> None:
    """An already-expired token is still checked no more than every 5 minutes."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch(
        "homeassistant.components.bluetti.oauth.async_track_point_in_time"
    ) as mock_track:
        refresher._schedule_next_check()

    scheduled_at = mock_track.call_args.args[2]
    delay = scheduled_at - dt_util.utcnow()
    assert timedelta(minutes=4, seconds=55) < delay < timedelta(minutes=5, seconds=5)


async def test_schedule_next_check_does_nothing_without_expires_at(
    hass: HomeAssistant,
) -> None:
    """Nothing to schedule against without an expires_at in the token."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {}
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch(
        "homeassistant.components.bluetti.oauth.async_track_point_in_time"
    ) as mock_track:
        refresher._schedule_next_check()

    mock_track.assert_not_called()


async def test_schedule_next_check_cancels_the_previous_one(
    hass: HomeAssistant,
) -> None:
    """Rescheduling must not leave the previous callback registered too."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 1000}
    refresher = AuthTokenRefresh(hass, entry, session)
    previous_unsub = MagicMock()
    refresher._unsub_next_check = previous_unsub

    with patch("homeassistant.components.bluetti.oauth.async_track_point_in_time"):
        refresher._schedule_next_check()

    previous_unsub.assert_called_once()


async def test_async_check_token_expiry_refresh_failure_is_logged(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry refresh failure is logged."""
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    # Must not raise even though the refresh call failed.
    await refresher.async_check_token_expiry()


async def test_async_get_access_token_ensures_validity_first() -> None:
    """Async get access token ensures validity first."""
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "fresh-token"}
    auth = AsyncConfigEntryAuth(MagicMock(), session)

    token = await auth.async_get_access_token()

    session.async_ensure_token_valid.assert_awaited_once()
    assert token == "fresh-token"


async def test_select_devices_shows_form_with_available_devices(
    hass: HomeAssistant,
) -> None:
    """Select devices shows form with available devices."""
    flow = BluettiConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow._oauth_data = {
        "auth_implementation": "bluetti",
        "token": {"access_token": "tok", "expires_at": 9999999999},
    }
    product = UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")

    with (
        patch("homeassistant.components.bluetti.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=MagicMock(data=[product])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "select_devices"
