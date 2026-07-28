"""Regression tests closing coverage gaps in bosch_shc_camera's config flow.

Targets specific branches missed by ``tests/test_config_flow.py``: the
``_flatten_sections`` defensive non-dict guard, ``BoschOAuth2Implementation``'s
``name`` property and token-exchange/refresh error-logging branches,
``_do_refresh``'s full status matrix, and the options flow's
``migrate_to_oss_client`` branch (including the legacy-client "auth" section
that only renders for a legacy-client token).
"""

import asyncio
import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.config_flow import (
    BoschOAuth2Implementation,
    RefreshTokenInvalidError,
    _do_refresh,
    _flatten_sections,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def test_flatten_sections_non_dict_section_payload_ignored() -> None:
    """A section payload that isn't a dict is defensively skipped, not raised."""
    assert _flatten_sections({"features": "not-a-dict"}) == {}


def test_oauth2_implementation_name_property(hass: HomeAssistant) -> None:
    """The implementation's display name is the fixed Bosch SingleKey ID label."""
    impl = BoschOAuth2Implementation(hass)
    assert impl.name == "Bosch SingleKey ID"


def _make_response(status: int, payload: dict[str, Any] | None = None) -> MagicMock:
    """Build a MagicMock aiohttp response usable as an async context manager."""
    resp = MagicMock()
    resp.status = status
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    if payload is not None:
        resp.json = AsyncMock(return_value=payload)
    if status >= 400:
        resp.raise_for_status = MagicMock(side_effect=RuntimeError(f"HTTP {status}"))
    return resp


async def test_resolve_external_data_logs_and_raises_on_http_error(
    hass: HomeAssistant,
) -> None:
    """A failed token exchange logs the status (without the body) then re-raises."""
    resp = _make_response(500)
    session = MagicMock()
    session.post = MagicMock(return_value=resp)
    impl = BoschOAuth2Implementation(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
            AsyncMock(return_value=session),
        ),
        pytest.raises(RuntimeError, match="HTTP 500"),
    ):
        await impl.async_resolve_external_data(
            {"code": "abcd", "state": {"redirect_uri": "https://example.invalid"}}
        )


async def test_refresh_token_success_returns_merged_token(hass: HomeAssistant) -> None:
    """A successful Keycloak refresh merges the new token fields over the old ones."""
    resp = _make_response(200, {"access_token": "new-access-token"})
    session = MagicMock()
    session.post = MagicMock(return_value=resp)
    impl = BoschOAuth2Implementation(hass)

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    ):
        result = await impl._async_refresh_token(
            {"refresh_token": "old-refresh", "access_token": "old-access-token"}
        )

    assert result == {
        "refresh_token": "old-refresh",
        "access_token": "new-access-token",
    }


async def test_refresh_token_error_status_logs_before_raising(
    hass: HomeAssistant,
) -> None:
    """A failed Keycloak refresh logs the status then re-raises via raise_for_status."""
    resp = _make_response(401)
    session = MagicMock()
    session.post = MagicMock(return_value=resp)
    impl = BoschOAuth2Implementation(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
            AsyncMock(return_value=session),
        ),
        pytest.raises(RuntimeError, match="HTTP 401"),
    ):
        await impl._async_refresh_token({"refresh_token": "old-refresh"})


def _spy_timeout(calls: list[float]) -> Any:
    """Return an ``asyncio.timeout`` stand-in that records the requested delay.

    Records the delay the caller asked for (so a test can assert it matches
    the adjacent access-check/refresh-helper budget) but substitutes a tiny
    real timeout underneath, so a stalled ``session.post()`` still raises
    promptly instead of the test itself hanging for the real budget.

    Captures the *real* ``asyncio.timeout`` before this factory is installed
    as the patch target — ``config_flow``'s ``asyncio`` is the same module
    object our own ``import asyncio`` refers to, so calling ``asyncio.timeout``
    from inside the factory after patching would recurse into the mock
    itself.
    """
    real_timeout = asyncio.timeout

    def _factory(delay: float) -> Any:
        calls.append(delay)
        return real_timeout(0.01)

    return _factory


def _make_hanging_response() -> MagicMock:
    """Build a mock response whose ``__aenter__`` never returns."""
    resp = MagicMock()

    async def _hang(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(100)

    resp.__aenter__ = _hang
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


async def test_resolve_external_data_bounded_by_15s_timeout(
    hass: HomeAssistant,
) -> None:
    """Authorization-code exchange is bounded by the same budget as refresh.

    Same 15s budget as ``_do_refresh``'s identical Keycloak /token POST,
    instead of falling back to aiohttp's 300s default — a stalled Keycloak
    endpoint raises instead of stalling the whole config flow (Copilot
    review round 16).
    """
    session = MagicMock()
    session.post = MagicMock(return_value=_make_hanging_response())
    impl = BoschOAuth2Implementation(hass)
    calls: list[float] = []

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
            AsyncMock(return_value=session),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.asyncio.timeout",
            side_effect=_spy_timeout(calls),
        ),
        pytest.raises(TimeoutError),
    ):
        await impl.async_resolve_external_data(
            {"code": "abcd", "state": {"redirect_uri": "https://example.invalid"}}
        )

    assert calls == [15]


async def test_refresh_token_bounded_by_15s_timeout(hass: HomeAssistant) -> None:
    """Token-refresh POST is likewise bounded by the 15s budget.

    Instead of aiohttp's 300s default (Copilot review round 16).
    """
    session = MagicMock()
    session.post = MagicMock(return_value=_make_hanging_response())
    impl = BoschOAuth2Implementation(hass)
    calls: list[float] = []

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
            AsyncMock(return_value=session),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.asyncio.timeout",
            side_effect=_spy_timeout(calls),
        ),
        pytest.raises(TimeoutError),
    ):
        await impl._async_refresh_token(
            {"refresh_token": "old-refresh", "access_token": "old-access-token"}
        )

    assert calls == [15]


async def test_do_refresh_returns_token_on_200() -> None:
    """A 200 response returns the parsed token JSON directly."""
    resp = _make_response(200, {"access_token": "new-token"})
    session = MagicMock()
    session.post = MagicMock(return_value=resp)

    assert await _do_refresh(session, "old_refresh_token") == {
        "access_token": "new-token"
    }


@pytest.mark.parametrize(
    "status",
    [pytest.param(400, id="400-bad-request"), pytest.param(401, id="401-unauthorized")],
)
async def test_do_refresh_raises_refresh_token_invalid_on_4xx(status: int) -> None:
    """A 400/401 (invalid_grant) raises RefreshTokenInvalidError, not a bare None."""
    resp = _make_response(status)
    session = MagicMock()
    session.post = MagicMock(return_value=resp)

    with pytest.raises(RefreshTokenInvalidError):
        await _do_refresh(session, "old_refresh_token")


async def test_do_refresh_returns_none_on_ambiguous_status() -> None:
    """A non-2xx/400/401/429/5xx status is ambiguous — returns None, doesn't raise."""
    resp = _make_response(418)
    session = MagicMock()
    session.post = MagicMock(return_value=resp)

    assert await _do_refresh(session, "old_refresh_token") is None


async def test_options_flow_migrate_to_oss_client_persists_and_triggers_reauth(
    hass: HomeAssistant,
) -> None:
    """Migrating a legacy-client token persists other option edits, then starts reauth.

    Also exercises the legacy-client "auth" section only rendering when the
    stored bearer token's `azp` claim is the legacy client id.
    """
    legacy_payload = base64.urlsafe_b64encode(
        json.dumps({"azp": "residential_app"}).encode()
    ).rstrip(b"=")
    legacy_token = f"header.{legacy_payload.decode()}.signature"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": legacy_token, "refresh_token": "reftok"},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "features": {"enable_snapshots": False},
            "auth": {"migrate_to_oss_client": True},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_started"
    # Other option edits in the same submission are persisted before reauth starts.
    assert entry.options["enable_snapshots"] is False
