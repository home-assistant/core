"""Test ViCare utils."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from PyViCare.PyViCareUtils import PyViCareRateLimitError

from homeassistant.components.vicare.utils import filter_state, retry_after_from

# From a real rate limit response: 2026-09-09T00:00:04.144Z.
QUOTA_RESET_MS = 1788912004144


@pytest.mark.parametrize(
    ("state", "expected_result"),
    [
        (None, None),
        ("unknown", None),
        ("nothing", None),
        ("levelOne", "levelOne"),
    ],
)
async def test_filter_state(
    state: str | None,
    expected_result: str | None,
) -> None:
    """Test filter_state."""

    assert filter_state(state) == expected_result


@pytest.mark.parametrize(
    ("now", "floor", "expected_result"),
    [
        ("2026-09-08 20:00:04+00:00", timedelta(seconds=60), 14400.144),
        # A reset already passed must not retry at once.
        ("2026-09-09 01:00:04+00:00", timedelta(seconds=60), 60),
        # The floor is the caller's interval, not a fixed minute.
        ("2026-09-09 01:00:04+00:00", timedelta(seconds=180), 180),
        # Nothing waits longer than the quota window.
        ("2026-09-06 00:00:04+00:00", timedelta(seconds=60), 86400),
    ],
)
async def test_retry_after_from(
    freezer: FrozenDateTimeFactory,
    now: str,
    floor: timedelta,
    expected_result: float,
) -> None:
    """Test the rate limit backoff is clamped to the caller's interval and a day."""
    freezer.move_to(now)
    error = PyViCareRateLimitError(
        {
            "extendedPayload": {
                "name": "development portal",
                "requestCountLimit": 1450,
                "limitReset": QUOTA_RESET_MS,
            }
        }
    )

    assert retry_after_from(error, floor) == expected_result
