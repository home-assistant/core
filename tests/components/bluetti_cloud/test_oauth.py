"""Tests for oauth.py: OAuth2FlowHandler helpers and AuthTokenRefresh."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti_cloud.const import DOMAIN, token_expired_signal
from homeassistant.components.bluetti_cloud.oauth import (
    AuthTokenRefresh,
    OAuth2FlowHandler,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers.dispatcher import async_dispatcher_send
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
    assert flow.logger.name == "homeassistant.components.bluetti_cloud.oauth"


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
    """The token-expired signal must actually fire, then stop after unload.

    Regression test: this test used to only fire the event and call
    async_block_till_done() with no assertion at all - it would still
    pass even if entry.async_on_unload(unsub) were never called, since
    nothing here ever checked the listener was subscribed, let alone
    unsubscribed.
    """
    refresher, entry = _refresher(hass, {})
    assert refresher.entry is entry

    with patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth:
        async_dispatcher_send(hass, token_expired_signal(entry.entry_id))
        await hass.async_block_till_done()
        mock_start_reauth.assert_called_once_with(hass)

        await entry._async_process_on_unload(hass)

        mock_start_reauth.reset_mock()
        async_dispatcher_send(hass, token_expired_signal(entry.entry_id))
        await hass.async_block_till_done()
        mock_start_reauth.assert_not_called()


async def test_on_token_expired_event_starts_reauth(hass: HomeAssistant) -> None:
    """On token expired event starts the standard reauth flow."""
    refresher, entry = _refresher(hass, {})

    with patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth:
        refresher.on_token_expired_event()

    mock_start_reauth.assert_called_once_with(hass)


async def test_start_token_check_runs_the_check_once(hass: HomeAssistant) -> None:
    """Start token check runs the check once, regardless of current validity."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() - 100})
    refresher.async_check_token_expiry = AsyncMock()

    refresher.start_token_check()
    await hass.async_block_till_done()

    refresher.async_check_token_expiry.assert_awaited_once()


async def test_async_check_token_expiry_no_expires_at_logs_and_returns(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry no expires at logs and returns."""
    refresher, _entry = _refresher(hass, {})

    # Must not raise even with nothing to check against.
    await refresher.async_check_token_expiry()


async def test_async_check_token_expiry_refreshes_an_already_expired_token(
    hass: HomeAssistant,
) -> None:
    """An already-expired access token must still be refreshed, not just skipped.

    Regression test: the already-expired branch used to notify immediately
    without ever attempting a refresh - an access token past its own
    (often much shorter) expiry is exactly the normal case a refresh token
    exists for, not necessarily a real problem.

    Also confirms the refresh does not reload the entry - a proactive
    background refresh persisting a new token must not tear down every
    device's coordinator and the websocket just to swap it in (see
    __init__.py: this integration registers no update listener).
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 10}
    session.implementation.async_refresh_token = AsyncMock(
        return_value={"access_token": "new"}
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await refresher.async_check_token_expiry()
        await hass.async_block_till_done()

    session.implementation.async_refresh_token.assert_awaited_once()
    mock_reload.assert_not_awaited()


async def test_async_check_token_expiry_not_due_soon_does_nothing(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry not due soon does nothing."""
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 3600 * 24 * 30})

    await refresher.async_check_token_expiry()


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


async def test_async_check_token_expiry_rate_limited_and_expired_does_nothing(
    hass: HomeAssistant,
) -> None:
    """A recently-refreshed but already-expired token just waits out the cooldown.

    Neither refreshes again (the 1-hour rate limit) nor treats this as a
    confirmed problem worth a repair signal - a real failure surfaces
    through the coordinator's own next poll if the token turns out to
    genuinely be bad.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, data={"last_token_refresh": time.time() - 60}
    )
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    refresher = AuthTokenRefresh(hass, entry, session)

    # Must not raise even though the token is already expired.
    await refresher.async_check_token_expiry()

    session.implementation.async_refresh_token.assert_not_called()


async def test_async_check_token_expiry_refreshes_without_reloading(
    hass: HomeAssistant,
) -> None:
    """Async check token expiry refreshes and persists the token without reloading.

    Regression test: async_check_token_expiry() used to call
    hass.config_entries.async_reload() explicitly right after
    async_update_entry(), and relied separately on a registered update
    listener to reload too - either one tearing down every device's
    coordinator and the websocket on a routine background token refresh.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
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
    mock_reload.assert_not_awaited()


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


async def test_async_check_token_expiry_starts_reauth_when_already_expired(
    hass: HomeAssistant,
) -> None:
    """An already-expired token with an invalid refresh token starts reauth too."""
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

    with patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth:
        await refresher.async_check_token_expiry()

    mock_start_reauth.assert_called_once_with(hass)


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
        "homeassistant.components.bluetti_cloud.oauth.async_track_point_in_time"
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
        "homeassistant.components.bluetti_cloud.oauth.async_track_point_in_time"
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
        "homeassistant.components.bluetti_cloud.oauth.async_track_point_in_time"
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
        "homeassistant.components.bluetti_cloud.oauth.async_track_point_in_time"
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

    with patch(
        "homeassistant.components.bluetti_cloud.oauth.async_track_point_in_time"
    ):
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
