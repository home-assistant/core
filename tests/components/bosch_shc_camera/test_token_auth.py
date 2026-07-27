"""Tests for token_auth.py's TokenAuthCoordinatorMixin refresh logic."""

import math
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.token_auth import (
    TokenAuthCoordinatorMixin,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


def _make_stub() -> SimpleNamespace:
    stub = SimpleNamespace(
        entry=SimpleNamespace(
            data={"refresh_token": "rtok", "bearer_token": "old-token"},
        ),
        hass=SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=MagicMock()),
        ),
        token="old-token",
        _token_still_valid=MagicMock(return_value=False),
        _token_fail_count=0,
        _token_timeout_fail_count=0,
        _token_alert_sent=False,
        auth_outage_count=0,
        _auth_outage_next_retry_ts=-math.inf,
        _auth_outage_alert_sent=False,
        schedule_token_refresh=MagicMock(),
    )
    # SimpleNamespace has no MRO to TokenAuthCoordinatorMixin, so
    # `self._handle_successful_refresh(...)` inside `_refresh_token_locked`
    # would otherwise AttributeError — bind the real method onto the stub.
    stub._handle_successful_refresh = types.MethodType(
        TokenAuthCoordinatorMixin._handle_successful_refresh, stub
    )
    return stub


async def _refresh(stub: SimpleNamespace) -> None:
    with patch(
        "homeassistant.components.bosch_shc_camera.token_auth.async_get_bosch_cloud_session",
        AsyncMock(return_value=MagicMock()),
    ):
        await TokenAuthCoordinatorMixin._refresh_token_locked(stub, "old-token")


@pytest.mark.asyncio
async def test_repeated_timeouts_never_trigger_reauth() -> None:
    """A refresh-timeout must stay transient (UpdateFailed) no matter how many times it repeats.

    It proves nothing about the refresh token's validity, unlike a genuine
    invalid-grant rejection (bug-hunt 2026-07-27, Copilot review round 4).
    """
    stub = _make_stub()

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(side_effect=TimeoutError()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.token_auth.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        for _ in range(5):
            with pytest.raises(UpdateFailed):
                await _refresh(stub)

    # 3 per-attempt retries per call — each one increments the counter.
    assert stub._token_timeout_fail_count == 15
    # The reauth-escalation counter must be completely untouched by timeouts.
    assert stub._token_fail_count == 0


@pytest.mark.asyncio
async def test_repeated_empty_responses_do_trigger_reauth() -> None:
    """A genuinely empty/malformed (non-timeout) refresh response is a real failure signal.

    It must still escalate to ConfigEntryAuthFailed after 3 consecutive
    occurrences.
    """
    stub = _make_stub()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
        AsyncMock(return_value=None),
    ):
        for _ in range(2):
            with pytest.raises(UpdateFailed):
                await _refresh(stub)
        with pytest.raises(ConfigEntryAuthFailed):
            await _refresh(stub)

    assert stub._token_fail_count == 3
    assert stub._token_timeout_fail_count == 0


@pytest.mark.asyncio
async def test_success_resets_both_counters() -> None:
    """A successful refresh clears both the timeout and reauth-escalation counters."""
    stub = _make_stub()
    stub._token_fail_count = 2
    stub._token_timeout_fail_count = 4

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
        AsyncMock(
            return_value={"access_token": "new-token", "refresh_token": "new-rtok"}
        ),
    ):
        await _refresh(stub)

    assert stub._token_fail_count == 0
    assert stub._token_timeout_fail_count == 0


@pytest.mark.asyncio
async def test_repeated_client_errors_never_trigger_reauth() -> None:
    """A network/DNS-class aiohttp.ClientError must stay transient too.

    `_do_refresh` used to swallow this into a bare `None` return,
    indistinguishable from an ambiguous HTTP response, so repeated DNS/
    connection failures still incremented `_token_fail_count` and
    eventually triggered unnecessary reauthentication despite the
    timeout-only fix (bug-hunt 2026-07-27, Copilot review round 5).
    """
    stub = _make_stub()

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(side_effect=aiohttp.ClientConnectionError("DNS failure")),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.token_auth.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        for _ in range(5):
            with pytest.raises(UpdateFailed):
                await _refresh(stub)

    assert stub._token_timeout_fail_count == 15
    assert stub._token_fail_count == 0
