"""Checker that enforces ``homeassistant.util.dt.naive_now`` over ``datetime.now()``.

Home Assistant exposes ``homeassistant.util.dt.naive_now`` -- a helper that
returns a naive ``datetime`` in system local time. Calling
``datetime.datetime.now()`` with no time zone argument does the same thing but
bypasses the helper. Using ``dt_util.naive_now`` keeps the codebase consistent
in how the current naive local time is obtained and documents that a naive
``datetime`` is intentional.

The aware cases (``datetime.now(tz)`` and ``datetime.now(UTC)``) are handled by
the ``home-assistant-enforce-now`` and ``home-assistant-enforce-utcnow``
checkers respectively.
"""

from pylint.lint import PyLinter

from pylint_home_assistant.helpers.datetime_now import (
    CASE_NAIVE,
    HassEnforceDatetimeNowChecker,
)


class HassEnforceNaiveNowChecker(HassEnforceDatetimeNowChecker):
    """Checker that flags ``datetime.now()`` calls without a time zone."""

    name = "home_assistant_enforce_naive_now"
    msgs = {
        "C7427": (
            "Use `homeassistant.util.dt.naive_now()` instead of `datetime.now()`",
            "home-assistant-enforce-naive-now",
            "Used when ``datetime.datetime.now()`` is called without a time zone "
            "to create a naive ``datetime`` in system local time. Use the "
            "``homeassistant.util.dt.naive_now`` helper instead. The aware cases "
            "are handled by the ``home-assistant-enforce-now`` and "
            "``home-assistant-enforce-utcnow`` checkers.",
        ),
    }

    message = "home-assistant-enforce-naive-now"
    flagged_case = CASE_NAIVE


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceNaiveNowChecker(linter))
