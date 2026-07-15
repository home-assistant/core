"""Bearer-token lifecycle: read/refresh/proactive-renewal + auth failure alerts.

Extracted from __init__.py's BoschCameraCoordinator (Phase 5 mixin split,
continuing the pattern established by FCMCoordinatorMixin/
FrigateCoordinatorMixin/SHCCoordinatorMixin — see those files' docstrings
for why `self: Any` is used instead of a concrete
`self: BoschCameraCoordinator` annotation).

Covers: the `token`/`refresh_token`/`options` properties (options included
here since it lives right alongside the token properties in the original
class and is equally trivial — a single `self._options_snapshot` read),
JWT-expiry checking, the locked refresh-token exchange against Keycloak
(with outage back-off + reauth-flow triggering), the one-time failure
alert (Repairs issue + notify), and the proactive refresh scheduler that
renews the token 5 minutes before it expires so normal ticks never hit a
reactive 401.
"""

import asyncio
import base64
import json
import logging
import time
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TokenAuthCoordinatorMixin:
    """Coordinator-facing bearer-token lifecycle methods."""

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def token(self: Any) -> str:
        """Return the current bearer token."""
        # Prefer in-memory refreshed token over config entry (avoids stale reads)
        return getattr(self, "_refreshed_token", None) or self.entry.data.get(  # type: ignore[no-any-return]  # value is correct at runtime; HA/external source is Any-typed
            "bearer_token", ""
        )

    @property
    def refresh_token(self: Any) -> str:
        """Return the current OAuth refresh token."""
        return getattr(self, "_refreshed_refresh", None) or self.entry.data.get(  # type: ignore[no-any-return]  # value is correct at runtime; HA/external source is Any-typed
            "refresh_token", ""
        )

    @property
    def options(self: Any) -> dict[str, Any]:
        """Return the config entry's options snapshot."""
        # [S7] _options_snapshot is valid for this coordinator's lifetime:
        # _async_options_updated always calls async_reload on real option changes,
        # rebuilding the coordinator with fresh options. No stale-read risk.
        return self._options_snapshot  # type: ignore[no-any-return]  # self: Any (mixin) — real type is dict[str, Any]

    # ── Token renewal ─────────────────────────────────────────────────────────
    def _token_still_valid(self: Any, min_remaining: int = 60) -> bool:
        """Return True if the in-memory bearer token is valid for >= min_remaining seconds.

        Used to skip unnecessary refreshes when a concurrent caller already
        refreshed the token while we were waiting on the lock.
        """
        token = self.token
        if not token:
            return False
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return False
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return bool((payload.get("exp", 0) - time.time()) >= min_remaining)
        except ValueError, TypeError:
            # JWT payload was not base64-decodable or not JSON — treat as expired.
            return False

    async def ensure_valid_token(self: Any, observed_token: str | None = None) -> str:
        """Return a valid bearer token.

        Called ONLY when we get a 401 — not on every tick.
        Refreshes via refresh_token with retry logic:
          - Serialized via self._token_refresh_lock so two concurrent
            callers never race on the same refresh_token (Keycloak
            rotates and invalidates the previous token on success —
            the loser of the race would get invalid_grant forever).
          - Skip-if-already-refreshed: after acquiring the lock, compare
            against `observed_token` (the token the caller saw fail);
            if it no longer matches `self.token`, another caller already
            refreshed it while we waited — reuse that instead of a redundant
            POST. Callers should always pass the token they observed to be
            bad. Bosch can reject a token (rotate/early-invalidate it) well
            before its own JWT `exp` claim says so — trusting `exp` alone
            (as this used to) meant a token rejected for any other reason
            was never actually refreshed: it still "looked" valid, so every
            retry just resent the same dead token forever (2026-07-06,
            SebastianHarder community report — a manual-login token was
            rejected immediately, and the integration never recovered).
          - Always re-read the freshest refresh_token from the
            config entry under the lock so we never send a stale
            token that was already rotated and persisted by the
            previous caller.
          - 3 attempts with 2s delay between retries
          - Persists new refresh token to config entry data (non-reloading)
          - Only alerts after 3 consecutive complete failures
        """
        async with self._token_refresh_lock:
            return await self._refresh_token_locked(observed_token)  # type: ignore[no-any-return]  # self: Any (mixin) — real type is str

    async def _refresh_token_locked(
        self: Any, observed_token: str | None = None
    ) -> str:
        # Local imports (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".ir.async_create_issue"/".ir.async_delete_issue") working the
        # same way it did before this method moved out of __init__.py —
        # those patches target the package's own namespace, not
        # token_auth.py's.
        from . import async_get_bosch_cloud_session, ir  # noqa: PLC0415

        # Real circular import if hoisted (verified): config_flow.py itself
        # does `from . import DEFAULT_OPTIONS, DOMAIN, BoschCameraConfigEntry`
        # at its own top level, which fails while this package's __init__.py
        # is still mid-import the first time coordinator.py -> token_auth.py
        # is reached.
        from .config_flow import (  # noqa: PLC0415
            AuthServerOutageError,
            RefreshTokenInvalidError,
            _do_refresh,
        )

        # Another caller may have just refreshed the token while we were
        # waiting on the lock — if so, skip the POST entirely. Prefer
        # comparing against the token the caller actually observed to be
        # bad (authoritative: a 401 already proves it); only fall back to
        # the JWT-expiry heuristic when no observed token was given.
        if observed_token is not None:
            if self.token != observed_token:
                return self.token  # type: ignore[no-any-return]  # self: Any (mixin) — real type is str
        elif self._token_still_valid(min_remaining=60):
            return self.token  # type: ignore[no-any-return]  # self: Any (mixin) — real type is str
        # If we're in a Bosch auth-server outage, skip the POST entirely
        # until the back-off gate opens — avoids hammering a server that
        # is already known to be down.
        now_m = time.monotonic()
        if self.auth_outage_count > 0 and now_m < self._auth_outage_next_retry_ts:
            remaining = int(self._auth_outage_next_retry_ts - now_m)
            raise UpdateFailed(
                f"Bosch auth server outage — next retry in {remaining}s "
                f"(outage count: {self.auth_outage_count})"
            )
        # Always prefer the freshest refresh_token from the config entry
        # (persisted by previous successful refresh) over our in-memory
        # copy, which could be stale in edge cases (e.g. entry reload).
        refresh = (
            self.entry.data.get("refresh_token", "")
            or getattr(self, "_refreshed_refresh", None)
            or ""
        )
        if not refresh:
            # No refresh token at all — trigger the built-in HA reauth button
            # (shows "Reconfigure" on the integration card, runs our auto-login).
            raise ConfigEntryAuthFailed("No refresh token — re-authentication required")
        session = await async_get_bosch_cloud_session(self.hass)
        # Retry up to 3 times with 2s delay on TRANSIENT errors only.
        # Hard auth errors (invalid_grant) raise RefreshTokenInvalidError
        # which we convert to ConfigEntryAuthFailed immediately — retrying
        # a rejected refresh token is pointless and just extends the user's
        # broken state.
        # Server outage (5xx) raises AuthServerOutageError — we back off
        # and retry later without triggering reauth (nothing for the user to fix).
        #
        # Outer 15s ceiling on the WHOLE retry loop (attempts + sleeps),
        # in addition to `_do_refresh`'s own per-attempt 15s timeout
        # (config_flow.py): defense in depth. Without this, a hanging
        # Keycloak response could still let 3 attempts x (15s timeout + 2s
        # sleep) = ~49s of _token_refresh_lock hold time, during which every
        # other caller of `_ensure_valid_token` (including all 401-recovery
        # paths in live_connection.py) blocks. Bounding the whole loop to a
        # single 15s ceiling caps the lock hold time regardless of how many
        # attempts were already spent, and stays correct even if
        # `_do_refresh`'s own timeout is ever changed or removed upstream.
        tokens = None
        try:
            async with asyncio.timeout(15):
                for attempt in range(3):
                    tokens = await _do_refresh(session, refresh)
                    if tokens:
                        break
                    if attempt < 2:
                        _LOGGER.debug(
                            "Token refresh attempt %d failed (transient), retrying in 2s...",
                            attempt + 1,
                        )
                        await asyncio.sleep(2)
        except TimeoutError:
            # The retry loop itself timed out (Keycloak unresponsive across
            # one or more attempts) — treat exactly like a transient failure
            # so the caller's fail-count/reauth escalation still applies,
            # but abort the loop early instead of letting it run to ~49s.
            self._token_fail_count += 1
            _LOGGER.warning(
                "Token refresh timed out after 15s (attempt %d) — Keycloak "
                "unresponsive, aborting retry loop early to release the "
                "token-refresh lock",
                self._token_fail_count,
            )
            if self._token_fail_count >= 3:
                raise ConfigEntryAuthFailed(
                    "Token refresh timed out repeatedly — please "
                    "re-authenticate via the Reconfigure button on the "
                    "integration card."
                ) from None
            raise UpdateFailed(
                "Token refresh timed out after 15s — will retry"
            ) from None
        except RefreshTokenInvalidError:
            # Do not log the exception body — Keycloak error responses can echo
            # token material back in the payload.
            _LOGGER.error(
                "Refresh token rejected by Keycloak (invalid_grant) — triggering reauth flow"
            )
            raise ConfigEntryAuthFailed(
                "Refresh token invalid — please re-authenticate via the "
                "Reconfigure button on the integration card."
            ) from None
        except AuthServerOutageError as err:
            self.auth_outage_count += 1
            # Exponential back-off: 60s, 120s, 240s, 480s, capped at 600s (10 min)
            backoff = min(60 * (2 ** (self.auth_outage_count - 1)), 600)
            self._auth_outage_next_retry_ts = now_m + backoff
            _LOGGER.warning(
                "Bosch Keycloak auth server outage (%s) — NOT triggering reauth "
                "(server-side problem, refresh token is probably still valid). "
                "Backing off %ds before next attempt (outage #%d).",
                err,
                backoff,
                self.auth_outage_count,
            )
            # One-time repair issue after 3 consecutive outages so the user
            # sees a clear explanation in Settings → Repairs while entities
            # are unavailable. Quality-Scale Gold rule `repair-issues`.
            if self.auth_outage_count >= 3 and not self._auth_outage_alert_sent:
                self._auth_outage_alert_sent = True
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "auth_server_outage",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="auth_server_outage",
                    translation_placeholders={"error": str(err)},
                )
            raise UpdateFailed(
                f"Bosch auth server outage — will retry in {backoff}s"
            ) from err
        if tokens:
            self._refreshed_token = tokens.get("access_token", "")
            new_refresh = tokens.get("refresh_token", refresh)
            self._refreshed_refresh = new_refresh
            _LOGGER.info("Bearer token renewed silently via refresh_token")
            # Always persist both tokens to config entry so they survive reloads/restarts.
            # Previously only saved when refresh_token changed — but Keycloak offline_access
            # keeps the same refresh_token, so the new bearer_token was never persisted.
            new_data = dict(self.entry.data)
            needs_update = False
            if new_refresh != self.entry.data.get("refresh_token", ""):
                new_data["refresh_token"] = new_refresh
                needs_update = True
            if self._refreshed_token != self.entry.data.get("bearer_token", ""):
                new_data["bearer_token"] = self._refreshed_token
                needs_update = True
            if needs_update:
                self.hass.config_entries.async_update_entry(self.entry, data=new_data)
                _LOGGER.debug("Persisted refreshed tokens to config entry")
            # Schedule next proactive refresh before this token expires
            self.schedule_token_refresh()
            # Reset failure tracking on success
            if self._token_fail_count > 0:
                _LOGGER.info(
                    "Token refresh recovered after %d failures", self._token_fail_count
                )
            self._token_fail_count = 0
            if self._token_alert_sent:
                self._token_alert_sent = False
                ir.async_delete_issue(self.hass, DOMAIN, "token_expired")
            # Clear auth-server outage state + dismiss the outage notification
            if self.auth_outage_count > 0:
                _LOGGER.info(
                    "Bosch auth server recovered after %d outage cycles",
                    self.auth_outage_count,
                )
                self.auth_outage_count = 0
                self._auth_outage_next_retry_ts = float("-inf")
                if self._auth_outage_alert_sent:
                    self._auth_outage_alert_sent = False
                    ir.async_delete_issue(self.hass, DOMAIN, "auth_server_outage")
            return self._refreshed_token  # type: ignore[no-any-return]
        self._token_fail_count += 1
        _LOGGER.warning(
            "Silent token renewal failed (attempt %d)", self._token_fail_count
        )
        # After 3 consecutive complete failures the refresh token is very
        # likely invalidated on Keycloak's side (invalid_grant). Trigger the
        # built-in HA reauth flow — a "Reconfigure" button appears on the
        # integration card, which runs the same auto-login flow and updates
        # the existing entry in place (keeps options, entities, automations).
        if self._token_fail_count >= 3:
            raise ConfigEntryAuthFailed(
                "Token refresh failed repeatedly — please re-authenticate via "
                "the Reconfigure button on the integration card."
            )
        raise UpdateFailed("Token refresh failed — will retry")

    async def _async_token_failure_alert(self: Any, message: str) -> None:
        """Send a one-time alert when token refresh fails (repair issue + notify)."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.ir.async_create_issue")
        # working the same way it did before this method moved out of
        # __init__.py.
        from . import ir  # noqa: PLC0415

        if self._token_alert_sent:
            return
        self._token_alert_sent = True
        title = "⚠️ Bosch Kamera — Token abgelaufen"
        # Repair issue — stays visible under Settings → Repairs until resolved.
        # Quality-Scale Gold rule `repair-issues` (replaces persistent_notification).
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "token_expired",
            is_fixable=False,
            severity=ir.IssueSeverity.CRITICAL,
            translation_key="token_expired",
            translation_placeholders={"message": message},
        )
        # Notify service (Signal, mobile_app, etc.) — uses system services
        for svc in self._get_alert_services("system"):
            domain, _, name = svc.partition(".")
            if self.hass.services.has_service(domain, name):
                try:
                    await self.hass.services.async_call(
                        domain,
                        name,
                        {"message": message, "title": title},
                    )
                    _LOGGER.info("Token failure alert sent via %s", svc)
                except Exception as err:  # noqa: BLE001 — best-effort alert fan-out to an arbitrary user-configured notify service; its failure modes are unknowable here and must never block iterating the remaining services
                    _LOGGER.debug("Token failure alert via %s failed: %s", svc, err)

    # ── Proactive background token refresh ───────────────────────────────────

    def schedule_token_refresh(self: Any) -> None:
        """Schedule a proactive token refresh 5 minutes before the JWT expires.

        Called after every successful token acquisition (startup + renewals).
        Ensures the token is always valid when automations or action methods run,
        eliminating the ~60s race window between token expiry and the next
        coordinator tick that previously triggered reactive 401 handling.
        """
        token = self.token
        if not token:
            return
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return
            # JWT payload is URL-safe base64 (no padding)
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            remaining = exp - time.time()
            # Refresh 5 minutes before expiry; at minimum 10s to avoid tight loops
            refresh_in = max(remaining - 300, 10)
            _LOGGER.debug(
                "Token expires in %.0fs — proactive refresh scheduled in %.0fs",
                remaining,
                refresh_in,
            )
            # Cancel any previously scheduled handle so reloads/reschedules
            # don't stack multiple timers that all fire the same refresh.
            prev = self.token_refresh_handle
            if prev is not None:
                try:
                    prev.cancel()
                except (AttributeError, RuntimeError) as err:
                    _LOGGER.debug(
                        "Could not cancel prior token-refresh handle: %s", err
                    )

            def _schedule_proactive_refresh() -> None:
                if self.hass.is_stopping:
                    return
                t = self.hass.async_create_task(self._proactive_refresh())
                self.bg_tasks.add(t)
                t.add_done_callback(self.bg_tasks.discard)

            self.token_refresh_handle = self.hass.loop.call_later(
                refresh_in,
                _schedule_proactive_refresh,
            )
        except (ValueError, TypeError, AttributeError) as err:
            _LOGGER.debug("_schedule_token_refresh: cannot parse token expiry: %s", err)

    async def _proactive_refresh(self: Any) -> None:
        """Background task: refresh the token before it expires."""
        if self.hass.is_stopping:
            return
        _LOGGER.debug("Proactive token refresh triggered")
        try:
            # Pass the current token as `observed_token` so the JWT-expiry
            # fallback (which would always say "still valid" here — this
            # fires 5 minutes BEFORE expiry by design) can't skip the
            # refresh; only a concurrent caller who already refreshed since
            # this timer fired should short-circuit it.
            await self.ensure_valid_token(self.token)
            # _ensure_valid_token calls _schedule_token_refresh on success,
            # so the next refresh is automatically rescheduled.
        except (ConfigEntryAuthFailed, UpdateFailed) as err:
            _LOGGER.warning(
                "Proactive token refresh failed: %s — will retry via reactive 401 handling",
                err,
            )
