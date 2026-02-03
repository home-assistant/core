"""Utility functions for Squeezebox integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


async def safe_library_call(
    method: Callable[..., Awaitable[Any]],
    *args: Any,
    translation_key: str,
    translation_placeholders: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Call a player method safely and raise HomeAssistantError on failure."""
    try:
        result = await method(*args, **kwargs)
    except ValueError:
        result = None

    if result is False or result is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )

    return result
