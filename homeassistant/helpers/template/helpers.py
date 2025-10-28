"""Template helper functions for Home Assistant."""

from __future__ import annotations

from typing import Any, NoReturn

from .context import template_cv


def raise_no_default(function: str, value: Any) -> NoReturn:
    """Raise ValueError when no default is specified for template functions."""
    template, action = template_cv.get() or ("", "rendering or compiling")
    raise ValueError(
        f"Template error: {function} got invalid input '{value}' when {action} template"
        f" '{template}' but no default was specified"
    )
