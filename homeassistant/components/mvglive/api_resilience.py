"""Retry, backoff and rate-limit handling around the mvg package's API calls.

The mvg package (https://pypi.org/project/mvg/) wraps every HTTP failure into a
plain ``MvgApiError`` with only a text message, so the HTTP status code isn't
available in a structured way and retry/backoff can't be added inside the
package itself. This module adds that resilience layer around calls to it.
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
import random
import re
import time
from typing import Any, TypeVar

from mvg import MvgApiError

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

_STATUS_RE = re.compile(r"\((\d{3})\)")

RATE_LIMIT_STATUS = 509
RETRYABLE_STATUSES = (502, 503)

_BASE_BACKOFF = 60.0
_MAX_BACKOFF = 600.0


@dataclass
class _RateLimitState:
    """Module-level (not per-coordinator) rate-limit state.

    A 509 from one station's poll should also pause polling for other
    stations, since MVG's rate limit is presumably per client/IP, not per
    station.
    """

    limited_until: float = 0.0
    backoff: float = _BASE_BACKOFF


_rate_limit_state = _RateLimitState()


def _extract_status_code(exc: MvgApiError) -> int | None:
    """Extract the HTTP status code from an MvgApiError's message, if any."""
    match = _STATUS_RE.search(str(exc))
    return int(match.group(1)) if match else None


async def call_with_resilience(
    factory: Callable[[], Coroutine[Any, Any, T]],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Call an mvg API coroutine factory with retry, backoff and rate-limit handling.

    :param factory: a callable producing a fresh coroutine on each call (a coroutine
        object can only be awaited once, so a factory is needed for retries)
    :param max_retries: number of retries for transient errors (502/503, network errors)
    :param base_delay: base delay in seconds for the exponential retry backoff
    :raises MvgApiError: if the call keeps failing, or a rate-limit cooldown is active
    """
    if time.monotonic() < _rate_limit_state.limited_until:
        raise MvgApiError(
            "MVG API is rate limited, skipping call until backoff expires"
        )

    for attempt in range(max_retries + 1):
        try:
            result = await factory()
        except MvgApiError as exc:
            status = _extract_status_code(exc)

            if status == RATE_LIMIT_STATUS:
                cooldown = _rate_limit_state.backoff
                _rate_limit_state.limited_until = time.monotonic() + cooldown
                _rate_limit_state.backoff = min(cooldown * 2, _MAX_BACKOFF)
                _LOGGER.warning(
                    "MVG API rate limit hit, backing off for %.0f seconds", cooldown
                )
                raise

            if (
                status in RETRYABLE_STATUSES or status is None
            ) and attempt < max_retries:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                _LOGGER.debug("MVG API call failed (%s), retrying in %.1fs", exc, delay)
                await asyncio.sleep(delay)
                continue

            raise
        else:
            _rate_limit_state.backoff = _BASE_BACKOFF
            return result

    raise AssertionError("unreachable")  # loop always returns or raises
