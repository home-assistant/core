"""Coverage-gap tests for tick_bootstrap.py's one-time bootstrap fetches."""

import asyncio
from typing import Any, Self

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.tick_bootstrap import (
    ensure_feature_flags,
    ensure_protocol_checked,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


class _RespCm:
    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        assert self._payload is not None
        return self._payload


class _RaisingCm:
    def __init__(self, err: BaseException) -> None:
        self._err = err

    async def __aenter__(self) -> Self:
        raise self._err

    async def __aexit__(self, *exc: object) -> None:
        return None


class _FakeSession:
    """Minimal aiohttp.ClientSession stand-in exposing only `.get`."""

    def __init__(self, response: object) -> None:
        self._response = response
        self.calls = 0

    def get(self, *_args: object, **_kwargs: object) -> object:
        self.calls += 1
        return self._response


async def test_ensure_feature_flags_skips_when_already_cached(
    hass: HomeAssistant,
) -> None:
    """A truthy `feature_flags` must skip the fetch entirely."""
    coordinator = _make_coordinator(hass)
    coordinator.feature_flags = {"foo": True}
    session = _FakeSession(_RaisingCm(AssertionError("must not fetch")))

    await ensure_feature_flags(coordinator, session, {})

    assert session.calls == 0
    assert coordinator.feature_flags == {"foo": True}


async def test_ensure_feature_flags_caches_successful_response(
    hass: HomeAssistant,
) -> None:
    """A 200 response is parsed and cached onto the coordinator."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RespCm(200, {"cool_feature": True}))

    await ensure_feature_flags(coordinator, session, {})

    assert coordinator.feature_flags == {"cool_feature": True}


async def test_ensure_feature_flags_non_200_leaves_flags_empty(
    hass: HomeAssistant,
) -> None:
    """A non-200 response must not populate `feature_flags`."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RespCm(500, None))

    await ensure_feature_flags(coordinator, session, {})

    assert coordinator.feature_flags == {}


@pytest.mark.parametrize(
    "err",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientError("boom"), id="client-error"),
    ],
)
async def test_ensure_feature_flags_swallows_fetch_errors(
    hass: HomeAssistant, err: BaseException
) -> None:
    """A fetch-time error must be swallowed — a missing fetch must not abort the tick."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RaisingCm(err))

    await ensure_feature_flags(coordinator, session, {})

    assert coordinator.feature_flags == {}


async def test_ensure_feature_flags_reraises_cancelled_error(
    hass: HomeAssistant,
) -> None:
    """A CancelledError must propagate, not be swallowed like other errors."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RaisingCm(asyncio.CancelledError()))

    with pytest.raises(asyncio.CancelledError):
        await ensure_feature_flags(coordinator, session, {})


async def test_ensure_protocol_checked_skips_when_already_checked(
    hass: HomeAssistant,
) -> None:
    """`protocol_checked=True` must skip the fetch entirely."""
    coordinator = _make_coordinator(hass)
    coordinator.protocol_checked = True
    session = _FakeSession(_RaisingCm(AssertionError("must not fetch")))

    await ensure_protocol_checked(coordinator, session, {})

    assert session.calls == 0


async def test_ensure_protocol_checked_supported_state_logs_debug(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A SUPPORTED response must not log a warning, and sets protocol_checked."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RespCm(200, {"state": "SUPPORTED"}))

    with caplog.at_level("WARNING"):
        await ensure_protocol_checked(coordinator, session, {})

    assert coordinator.protocol_checked is True
    assert "may no longer be supported" not in caplog.text


async def test_ensure_protocol_checked_unsupported_state_logs_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-SUPPORTED state must log a warning about the protocol version."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RespCm(200, {"state": "DEPRECATED"}))

    with caplog.at_level("WARNING"):
        await ensure_protocol_checked(coordinator, session, {})

    assert coordinator.protocol_checked is True
    assert "may no longer be supported" in caplog.text


async def test_ensure_protocol_checked_non_200_logs_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-200 status must log a warning with the HTTP status."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RespCm(503, None))

    with caplog.at_level("WARNING"):
        await ensure_protocol_checked(coordinator, session, {})

    assert coordinator.protocol_checked is True
    assert "returned HTTP 503" in caplog.text


@pytest.mark.parametrize(
    "err",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientError("boom"), id="client-error"),
        pytest.param(ValueError("bad json"), id="value-error"),
    ],
)
async def test_ensure_protocol_checked_swallows_fetch_errors(
    hass: HomeAssistant, err: BaseException
) -> None:
    """A fetch-time error must be swallowed — the check must never raise."""
    coordinator = _make_coordinator(hass)
    session = _FakeSession(_RaisingCm(err))

    await ensure_protocol_checked(coordinator, session, {})

    assert coordinator.protocol_checked is True
