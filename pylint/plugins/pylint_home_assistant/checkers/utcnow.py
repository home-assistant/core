"""Checker that enforces ``homeassistant.util.dt.utcnow`` over ``datetime.now(UTC)``.

Home Assistant exposes ``homeassistant.util.dt.utcnow`` -- a thin wrapper around
``datetime.datetime.now(UTC)`` implemented as a ``functools.partial``. Using the
helper avoids the per-call global lookup of ``UTC`` and keeps the codebase
consistent in how the current UTC time is obtained.
"""

from pylint.lint import PyLinter

from pylint_home_assistant.helpers.datetime_now import (
    CASE_UTC,
    HassEnforceDatetimeNowChecker,
)


class HassEnforceUtcnowChecker(HassEnforceDatetimeNowChecker):
    """Checker that flags ``datetime.now(UTC)`` calls."""

    name = "home_assistant_enforce_utcnow"
    msgs = {
        "C7414": (
            "Use `homeassistant.util.dt.utcnow()` instead of `datetime.now(UTC)`",
            "home-assistant-enforce-utcnow",
            "Used when ``datetime.datetime.now(UTC)`` is called. Use the "
            "``homeassistant.util.dt.utcnow`` helper instead -- it is "
            "implemented as ``functools.partial(datetime.datetime.now, UTC)`` "
            "and avoids the global lookup of ``UTC`` on every call.",
        ),
    }

    message = "home-assistant-enforce-utcnow"
    flagged_case = CASE_UTC


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceUtcnowChecker(linter))
