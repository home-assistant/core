"""Regression tests closing patch-coverage gaps in camera_list.py.

Companion to test_camera_list.py — kept in a separate file to avoid
collisions with other agents editing the existing test module in parallel.
`fetch_camera_list` takes the coordinator as a plain parameter (it is not an
entity), so a `SimpleNamespace`/`MagicMock` stub coordinator is the
established pattern for it (see test_camera_list.py) — this is not the
Entity-construction-bypass anti-pattern flagged elsewhere on this PR.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.camera_list import fetch_camera_list
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

_MOD = "homeassistant.components.bosch_shc_camera.camera_list"


def _resp_cm(status: int, text: str = "", json_data: object = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.json = AsyncMock(return_value=json_data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_coordinator(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "ensure_valid_token": AsyncMock(return_value="fresh-token"),
        "async_outage_ping_all": AsyncMock(),
        "spawn_tracked": MagicMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def test_first_response_200_returns_cam_list_immediately() -> None:
    """The plain, no-retry success path: a 200 on the very first call."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(200, json_data=[{"id": "cam-1"}]))

    cam_list, token, _headers = await fetch_camera_list(
        coordinator, session, {"Accept": "application/json"}, "tok"
    )

    assert cam_list == [{"id": "cam-1"}]
    assert token == "tok"
    session.get.assert_called_once()


async def test_timeout_on_first_attempt_retries_and_succeeds() -> None:
    """A bare timeout on attempt 1/2 retries once (after the configured delay) and succeeds."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[TimeoutError, _resp_cm(200, json_data=[{"id": "cam-1"}])]
    )

    with patch(f"{_MOD}.asyncio.sleep", AsyncMock()) as mock_sleep:
        cam_list, _token, _headers = await fetch_camera_list(
            coordinator, session, {}, "tok"
        )

    assert cam_list == [{"id": "cam-1"}]
    mock_sleep.assert_called_once()


async def test_timeout_on_both_attempts_raises() -> None:
    """A timeout on both attempts propagates instead of being retried a third time."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(side_effect=[TimeoutError, TimeoutError])

    with (
        patch(f"{_MOD}.asyncio.sleep", AsyncMock()),
        pytest.raises(TimeoutError),
    ):
        await fetch_camera_list(coordinator, session, {}, "tok")


async def test_401_then_renewal_retry_succeeds() -> None:
    """A 401 renews the token and the retry succeeds with a fresh 200."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _resp_cm(401, text="expired"),
            _resp_cm(200, json_data=[{"id": "cam-2"}]),
        ]
    )

    cam_list, token, headers = await fetch_camera_list(
        coordinator, session, {"Accept": "application/json"}, "stale-tok"
    )

    assert cam_list == [{"id": "cam-2"}]
    assert token == "fresh-token"
    assert headers["Authorization"] == "Bearer fresh-token"
    coordinator.ensure_valid_token.assert_called_once_with("stale-tok")


async def test_401_then_retry_still_401_with_sh_authorization_failed_raises_update_failed() -> (
    None
):
    """A Bosch account/permission rejection must not be treated as a token problem."""
    coordinator = _make_coordinator()
    body = json.dumps({"error": "sh:authorization.failed", "message": "missing perm"})
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[_resp_cm(401, text="expired"), _resp_cm(401, text=body)]
    )

    with pytest.raises(UpdateFailed, match="sh:authorization.failed"):
        await fetch_camera_list(coordinator, session, {}, "tok")


async def test_401_then_retry_still_401_with_unparseable_body_raises_auth_failed() -> (
    None
):
    """A still-401 retry with a non-JSON body falls through to the generic reauth path."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _resp_cm(401, text="expired"),
            _resp_cm(401, text="not json at all"),
        ]
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await fetch_camera_list(coordinator, session, {}, "tok")


async def test_401_then_retry_still_401_generic_error_raises_auth_failed() -> None:
    """A genuinely renewed-then-still-rejected token requires reauthentication."""
    coordinator = _make_coordinator()
    body = json.dumps({"error": "some.other.error", "message": "whatever"})
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[_resp_cm(401, text="expired"), _resp_cm(401, text=body)]
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await fetch_camera_list(coordinator, session, {}, "tok")


async def test_401_then_retry_non_200_non_401_raises_update_failed() -> None:
    """A retry response that's neither 200 nor 401 (e.g. a 500) fails the tick."""
    coordinator = _make_coordinator()
    session = MagicMock()
    session.get = MagicMock(side_effect=[_resp_cm(401, text="expired"), _resp_cm(500)])

    with pytest.raises(UpdateFailed, match="500"):
        await fetch_camera_list(coordinator, session, {}, "tok")
