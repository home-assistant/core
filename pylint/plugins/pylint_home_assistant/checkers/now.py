"""Checker that enforces ``homeassistant.util.dt.now`` over ``datetime.now(tz)``.

Home Assistant exposes ``homeassistant.util.dt.now`` -- a helper that returns an
aware ``datetime`` in the given time zone (defaulting to ``DEFAULT_TIME_ZONE``).
Calling ``datetime.datetime.now(tz)`` directly with a time zone argument does the
same thing but bypasses the helper. Using ``dt_util.now`` keeps the codebase
consistent in how the current local time is obtained.

The UTC special case (``datetime.now(UTC)``) is intentionally left to the
``home-assistant-enforce-utcnow`` checker, which steers it to the faster
``dt_util.utcnow`` partial. ``datetime.now()`` with no argument returns a naive
local ``datetime`` and is therefore not equivalent to ``dt_util.now()``; it is not
flagged.
"""

from pylint.lint import PyLinter

from pylint_home_assistant.helpers.datetime_now import (
    CASE_OTHER,
    HassEnforceDatetimeNowChecker,
)


class HassEnforceNowChecker(HassEnforceDatetimeNowChecker):
    """Checker that flags ``datetime.now(tz)`` calls with a non-UTC time zone."""

    name = "home_assistant_enforce_now"
    msgs = {
        "C7425": (
            "Use `homeassistant.util.dt.now()` instead of `datetime.now(<tz>)`",
            "home-assistant-enforce-now",
            "Used when ``datetime.datetime.now(<tz>)`` is called with a non-UTC "
            "time zone to create an aware ``datetime``. Use the "
            "``homeassistant.util.dt.now`` helper instead. The UTC case is "
            "handled by the ``home-assistant-enforce-utcnow`` checker.",
        ),
    }

    message = "home-assistant-enforce-now"
    flagged_case = CASE_OTHER


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceNowChecker(linter))
