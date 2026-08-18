"""Test the retry/backoff/rate-limit wrapper around the mvg API."""

from unittest.mock import AsyncMock

from mvg import MvgApiError
import pytest

from homeassistant.components.mvglive import api_resilience


@pytest.fixture(autouse=True)
def _reset_rate_limit_state() -> None:
    """Reset the module-level rate-limit state between tests."""
    api_resilience._rate_limit_state.limited_until = 0.0
    api_resilience._rate_limit_state.backoff = api_resilience._BASE_BACKOFF


async def test_retries_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a retryable error is retried and eventually succeeds."""
    monkeypatch.setattr(api_resilience.asyncio, "sleep", AsyncMock())
    factory = AsyncMock(
        side_effect=[MvgApiError("Bad API call: Got response (502)"), "ok"]
    )

    result = await api_resilience.call_with_resilience(factory)

    assert result == "ok"
    assert factory.call_count == 2


async def test_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that retries are bounded by max_retries."""
    monkeypatch.setattr(api_resilience.asyncio, "sleep", AsyncMock())
    factory = AsyncMock(side_effect=MvgApiError("Bad API call: Got response (502)"))

    with pytest.raises(MvgApiError):
        await api_resilience.call_with_resilience(factory, max_retries=2)

    assert factory.call_count == 3


async def test_rate_limit_cooldown_matches_logged_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the applied cooldown matches the value used in the warning log.

    Regression test: the cooldown used to be computed from the pre-doubled
    backoff, but the log message reported the already-doubled value.
    """
    monkeypatch.setattr(api_resilience.time, "monotonic", lambda: 1000.0)
    factory = AsyncMock(side_effect=MvgApiError("Bad API call: Got response (509)"))

    with pytest.raises(MvgApiError):
        await api_resilience.call_with_resilience(factory)

    expected_cooldown = api_resilience._BASE_BACKOFF
    assert api_resilience._rate_limit_state.limited_until == 1000.0 + expected_cooldown
    assert api_resilience._rate_limit_state.backoff == expected_cooldown * 2


async def test_rate_limit_blocks_subsequent_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a call made during an active cooldown is rejected without retrying."""
    monkeypatch.setattr(api_resilience.time, "monotonic", lambda: 1000.0)
    api_resilience._rate_limit_state.limited_until = 1001.0
    factory = AsyncMock()

    with pytest.raises(MvgApiError, match="rate limited"):
        await api_resilience.call_with_resilience(factory)

    factory.assert_not_called()
