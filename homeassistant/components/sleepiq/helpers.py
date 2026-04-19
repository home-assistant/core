"""Helpers for the SleepIQ integration."""

from __future__ import annotations

from asyncsleepiq import SleepIQLoginException

INVALID_AUTH_ERROR = "incorrect username or password"


def is_invalid_auth(err: SleepIQLoginException) -> bool:
    """Return if a SleepIQ login exception indicates invalid credentials."""
    return INVALID_AUTH_ERROR in str(err).lower()
