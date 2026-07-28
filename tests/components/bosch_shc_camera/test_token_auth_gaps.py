"""Patch-coverage gap tests for token_auth.py.

Exercises `TokenAuthCoordinatorMixin` through a real `BoschCameraCoordinator`
built from a `MockConfigEntry` (matching `test_token_auth.py`'s established
style — bug-hunt 2026-07-27, Copilot review round 6 flagged the
bare-SimpleNamespace-mixin-bypass anti-pattern), not a bare SimpleNamespace.
"""

import base64
import json
import time
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.config_flow import (
    CLIENT_ID,
    CLIENT_SECRET,
    AuthServerOutageError,
    RefreshTokenInvalidError,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _jwt(exp_offset: float) -> str:
    """Build a fake (unsigned) JWT with the given expiry offset from now."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": time.time() + exp_offset}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.sig"


def _make_coordinator(
    hass: HomeAssistant, *, bearer_token: str = "old-token"
) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": bearer_token, "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


async def _refresh(coord: BoschCameraCoordinator, observed: str | None) -> str:
    with patch(
        "homeassistant.components.bosch_shc_camera.token_auth.async_get_bosch_cloud_session",
        AsyncMock(return_value=MagicMock()),
    ):
        return await coord.ensure_valid_token(observed)


class TestTokenStillValid:
    """`_token_still_valid`'s JWT-decode edge cases (lines 107-119)."""

    @pytest.mark.asyncio
    async def test_no_token_is_invalid(self, hass: HomeAssistant) -> None:
        """An empty bearer token is never valid."""
        coord = _make_coordinator(hass, bearer_token="")
        assert coord._token_still_valid() is False

    @pytest.mark.asyncio
    async def test_malformed_token_missing_payload_segment(
        self, hass: HomeAssistant
    ) -> None:
        """A token with no `.` separator (single segment) is invalid."""
        coord = _make_coordinator(hass, bearer_token="not-a-jwt")
        assert coord._token_still_valid() is False

    @pytest.mark.asyncio
    async def test_undecodable_payload_is_invalid(self, hass: HomeAssistant) -> None:
        """A payload segment that isn't valid base64/JSON is treated as expired."""
        coord = _make_coordinator(hass, bearer_token="header.!!!not-base64!!!.sig")
        assert coord._token_still_valid() is False

    @pytest.mark.asyncio
    async def test_valid_unexpired_token(self, hass: HomeAssistant) -> None:
        """A JWT with a future `exp` claim is valid."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        assert coord._token_still_valid(min_remaining=60) is True

    @pytest.mark.asyncio
    async def test_expired_token_is_invalid(self, hass: HomeAssistant) -> None:
        """A JWT with a past `exp` claim is invalid."""
        coord = _make_coordinator(hass, bearer_token=_jwt(-3600))
        assert coord._token_still_valid() is False


class TestObservedTokenAlreadyRefreshed:
    """A concurrent caller already refreshed the token before the lock (lines 249-253)."""

    @pytest.mark.asyncio
    async def test_returns_current_token_without_refreshing(
        self, hass: HomeAssistant
    ) -> None:
        """observed_token no longer matching self.token skips the refresh POST."""
        coord = _make_coordinator(hass, bearer_token="current-token")

        with patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(),
        ) as mock_refresh:
            out = await _refresh(coord, "stale-observed-token")

        assert out == "current-token"
        mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_observed_token_falls_back_to_jwt_expiry_check(
        self, hass: HomeAssistant
    ) -> None:
        """No observed_token given: an unexpired JWT skips the refresh via `_token_still_valid`."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))

        with patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(),
        ) as mock_refresh:
            out = await _refresh(coord, None)

        assert out == coord.token
        mock_refresh.assert_not_called()


class TestNoRefreshToken:
    """No refresh token at all triggers reauth (lines 272-275)."""

    @pytest.mark.asyncio
    async def test_missing_refresh_token_raises_auth_failed(
        self, hass: HomeAssistant
    ) -> None:
        """Empty refresh_token raises ConfigEntryAuthFailed, not a POST attempt."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={"bearer_token": "old-token", "refresh_token": ""},
            options={},
        )
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        with pytest.raises(ConfigEntryAuthFailed):
            await _refresh(coord, "old-token")


class TestAuthOutageGate:
    """The back-off gate skips the POST entirely while in an outage window (lines 258-263)."""

    @pytest.mark.asyncio
    async def test_gate_active_raises_update_failed_without_posting(
        self, hass: HomeAssistant
    ) -> None:
        """A still-open back-off window raises UpdateFailed, no HTTP attempt made."""
        coord = _make_coordinator(hass)
        coord.auth_outage_count = 2
        coord._auth_outage_next_retry_ts = time.monotonic() + 120

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(),
            ) as mock_refresh,
            pytest.raises(UpdateFailed, match="outage"),
        ):
            await _refresh(coord, "old-token")

        mock_refresh.assert_not_called()


class TestCustomAuthImplementation:
    """A non-default auth_implementation resolves its own client credential (lines 229-239)."""

    @pytest.mark.asyncio
    async def test_custom_credential_used_for_refresh(
        self, hass: HomeAssistant
    ) -> None:
        """When entry.data['auth_implementation'] != DOMAIN, its own client id/secret are used."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={
                "bearer_token": "old-token",
                "refresh_token": "rtok",
                "auth_implementation": "custom_impl",
            },
            options={},
        )
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        credential = MagicMock(client_id="custom-id", client_secret="custom-secret")
        component = MagicMock()
        component.async_client_credentials.return_value = {"custom_impl": credential}

        with (
            patch(
                "homeassistant.components.application_credentials.DATA_COMPONENT",
                "ac_component_key",
            ),
            patch.object(hass, "data", {"ac_component_key": component}),
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(
                    return_value={
                        "access_token": "new-token",
                        "refresh_token": "new-rtok",
                    }
                ),
            ) as mock_refresh,
        ):
            out = await _refresh(coord, "old-token")

        assert out == "new-token"
        assert mock_refresh.call_args.args[2] == "custom-id"
        assert mock_refresh.call_args.args[3] == "custom-secret"

    @pytest.mark.asyncio
    async def test_custom_credential_missing_falls_back_to_default(
        self, hass: HomeAssistant
    ) -> None:
        """A custom auth_implementation with no registered credential keeps the default client."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={
                "bearer_token": "old-token",
                "refresh_token": "rtok",
                "auth_implementation": "custom_impl",
            },
            options={},
        )
        entry.add_to_hass(hass)
        coord = BoschCameraCoordinator(hass, entry)

        component = MagicMock()
        component.async_client_credentials.return_value = {}

        with (
            patch(
                "homeassistant.components.application_credentials.DATA_COMPONENT",
                "ac_component_key",
            ),
            patch.object(hass, "data", {"ac_component_key": component}),
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(
                    return_value={
                        "access_token": "new-token",
                        "refresh_token": "new-rtok",
                    }
                ),
            ) as mock_refresh,
        ):
            await _refresh(coord, "old-token")

        assert mock_refresh.call_args.args[2] == CLIENT_ID
        assert mock_refresh.call_args.args[3] == CLIENT_SECRET


class TestRefreshExceptionPaths:
    """The three named exception branches of `_refresh_token_locked` (lines 318-368)."""

    @pytest.mark.asyncio
    async def test_outer_timeout_aborts_early(self, hass: HomeAssistant) -> None:
        """The outer 15s ceiling timing out raises UpdateFailed, not a hang."""
        coord = _make_coordinator(hass)

        class _ImmediateTimeout:
            async def __aenter__(self) -> Self:
                raise TimeoutError

            async def __aexit__(self, *exc: object) -> bool:
                return False

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.token_auth.asyncio.timeout",
                lambda _seconds: _ImmediateTimeout(),
            ),
            pytest.raises(UpdateFailed, match="timed out"),
        ):
            await _refresh(coord, "old-token")

        assert coord._token_timeout_fail_count == 1

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_triggers_reauth(
        self, hass: HomeAssistant
    ) -> None:
        """A Keycloak invalid_grant rejection converts straight to ConfigEntryAuthFailed."""
        coord = _make_coordinator(hass)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(side_effect=RefreshTokenInvalidError("invalid_grant")),
            ),
            pytest.raises(ConfigEntryAuthFailed),
        ):
            await _refresh(coord, "old-token")

    @pytest.mark.asyncio
    async def test_auth_server_outage_backs_off_without_reauth(
        self, hass: HomeAssistant
    ) -> None:
        """A server-side outage raises UpdateFailed and starts the back-off counter."""
        coord = _make_coordinator(hass)

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(side_effect=AuthServerOutageError("503")),
            ),
            pytest.raises(UpdateFailed, match="outage"),
        ):
            await _refresh(coord, "old-token")

        assert coord.auth_outage_count == 1
        assert coord._auth_outage_next_retry_ts > time.monotonic()


class TestSuccessClearsAlertAndOutage:
    """A successful refresh clears the token-alert Repairs issue + outage state (lines 192-201)."""

    @pytest.mark.asyncio
    async def test_success_deletes_issue_and_resets_outage(
        self, hass: HomeAssistant
    ) -> None:
        """Both `_token_alert_sent` and `auth_outage_count` are cleared on success."""
        coord = _make_coordinator(hass)
        coord._token_alert_sent = True
        coord.auth_outage_count = 3

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
                AsyncMock(
                    return_value={
                        "access_token": "new-token",
                        "refresh_token": "new-rtok",
                    }
                ),
            ),
            patch(
                "homeassistant.components.bosch_shc_camera.token_auth.ir.async_delete_issue"
            ) as mock_delete_issue,
        ):
            await _refresh(coord, "old-token")

        assert coord._token_alert_sent is False
        assert coord.auth_outage_count == 0
        mock_delete_issue.assert_called_once_with(hass, DOMAIN, "token_expired")


class TestTokenFailureAlert:
    """`_async_token_failure_alert` (lines 409-436)."""

    @pytest.mark.asyncio
    async def test_second_call_is_a_no_op(self, hass: HomeAssistant) -> None:
        """Once an alert was sent, a repeat call does nothing."""
        coord = _make_coordinator(hass)
        coord._token_alert_sent = True

        with patch(
            "homeassistant.components.bosch_shc_camera.token_auth.ir.async_create_issue"
        ) as mock_create_issue:
            await coord._async_token_failure_alert("still broken")

        mock_create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_issue_and_notifies_configured_services(
        self, hass: HomeAssistant
    ) -> None:
        """A fresh alert creates a Repairs issue and calls every configured notify service."""
        coord = _make_coordinator(hass)
        coord._token_alert_sent = False
        coord._get_alert_services = MagicMock(return_value=["notify.mobile_app"])

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.token_auth.ir.async_create_issue"
            ) as mock_create_issue,
            patch.object(
                type(hass.services), "has_service", MagicMock(return_value=True)
            ),
            patch.object(type(hass.services), "async_call", AsyncMock()) as mock_call,
        ):
            await coord._async_token_failure_alert("token expired")

        assert coord._token_alert_sent is True
        mock_create_issue.assert_called_once()
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_service_failure_does_not_raise(
        self, hass: HomeAssistant
    ) -> None:
        """One notify target raising must not abort the alert or other targets."""
        coord = _make_coordinator(hass)
        coord._token_alert_sent = False
        coord._get_alert_services = MagicMock(return_value=["notify.broken_target"])

        with (
            patch(
                "homeassistant.components.bosch_shc_camera.token_auth.ir.async_create_issue"
            ),
            patch.object(
                type(hass.services), "has_service", MagicMock(return_value=True)
            ),
            patch.object(
                type(hass.services),
                "async_call",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            await coord._async_token_failure_alert("token expired")

        assert coord._token_alert_sent is True


class TestScheduleTokenRefresh:
    """`schedule_token_refresh` (lines 448-490)."""

    @pytest.mark.asyncio
    async def test_no_token_does_not_schedule(self, hass: HomeAssistant) -> None:
        """An empty token schedules nothing."""
        coord = _make_coordinator(hass, bearer_token="")
        coord.token_refresh_handle = None

        coord.schedule_token_refresh()

        assert coord.token_refresh_handle is None

    @pytest.mark.asyncio
    async def test_schedules_a_call_later_handle(self, hass: HomeAssistant) -> None:
        """A valid token schedules a real `call_later` handle, cancelling any prior one."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        prev_handle = MagicMock()
        coord.token_refresh_handle = prev_handle

        coord.schedule_token_refresh()

        prev_handle.cancel.assert_called_once()
        assert coord.token_refresh_handle is not None
        assert coord.token_refresh_handle is not prev_handle
        coord.token_refresh_handle.cancel()

    @pytest.mark.asyncio
    async def test_call_later_callback_spawns_tracked_proactive_refresh(
        self, hass: HomeAssistant
    ) -> None:
        """Firing the scheduled callback creates a tracked background task (lines 478-483)."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        coord.ensure_valid_token = AsyncMock(return_value="new-token")
        captured: dict[str, object] = {}

        def _fake_call_later(_delay: float, callback: object) -> MagicMock:
            captured["cb"] = callback
            return MagicMock()

        with patch.object(hass.loop, "call_later", side_effect=_fake_call_later):
            coord.schedule_token_refresh()

        captured["cb"]()  # type: ignore[operator]
        await hass.async_block_till_done()

        coord.ensure_valid_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_later_callback_noop_if_stopping_by_fire_time(
        self, hass: HomeAssistant
    ) -> None:
        """Hass stopping by the time the timer fires must skip spawning a task."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        captured: dict[str, object] = {}

        def _fake_call_later(_delay: float, callback: object) -> MagicMock:
            captured["cb"] = callback
            return MagicMock()

        with patch.object(hass.loop, "call_later", side_effect=_fake_call_later):
            coord.schedule_token_refresh()

        coord.hass = MagicMock(is_stopping=True)
        captured["cb"]()  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_prior_handle_cancel_error_is_swallowed(
        self, hass: HomeAssistant
    ) -> None:
        """A prior handle raising on cancel() (already fired) must not abort rescheduling."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        prev_handle = MagicMock()
        prev_handle.cancel.side_effect = RuntimeError("already cancelled")
        coord.token_refresh_handle = prev_handle

        coord.schedule_token_refresh()

        assert coord.token_refresh_handle is not None
        coord.token_refresh_handle.cancel()

    @pytest.mark.asyncio
    async def test_malformed_token_is_silently_ignored(
        self, hass: HomeAssistant
    ) -> None:
        """A token whose payload can't be parsed logs debug and schedules nothing."""
        coord = _make_coordinator(hass, bearer_token="header.!!!bad!!!.sig")
        coord.token_refresh_handle = None

        coord.schedule_token_refresh()

        assert coord.token_refresh_handle is None


class TestProactiveRefresh:
    """`_proactive_refresh` background task (lines 494-507)."""

    @pytest.mark.asyncio
    async def test_noop_while_hass_is_stopping(self, hass: HomeAssistant) -> None:
        """Hass shutting down skips the refresh entirely.

        Only the coordinator's own `.hass` reference is swapped for a stub —
        the shared `hass` test fixture is left untouched so its normal
        teardown isn't affected by a fake "stopping" state.
        """
        coord = _make_coordinator(hass)
        coord.hass = MagicMock(is_stopping=True)

        await coord._proactive_refresh()

    @pytest.mark.asyncio
    async def test_successful_refresh_calls_ensure_valid_token(
        self, hass: HomeAssistant
    ) -> None:
        """A normal proactive tick refreshes via ensure_valid_token with the current token."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        coord.ensure_valid_token = AsyncMock(return_value="new-token")

        await coord._proactive_refresh()

        coord.ensure_valid_token.assert_called_once_with(coord.token)

    @pytest.mark.asyncio
    async def test_failure_is_caught_and_logged(self, hass: HomeAssistant) -> None:
        """Any exception from ensure_valid_token must not escape the background task."""
        coord = _make_coordinator(hass, bearer_token=_jwt(3600))
        coord.ensure_valid_token = AsyncMock(side_effect=RuntimeError("boom"))

        await coord._proactive_refresh()
