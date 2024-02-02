"""Helpers to redact Google Assistant data when logging."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.redact import async_redact_data, partial_redact

SYNC_MSG_TO_REDACT: dict[str, Callable[[str], str]] = {
    "agentUserId": partial_redact,
    "uuid": partial_redact,
    "webhookId": partial_redact,
}


@callback
def async_redact_sync_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive data in sync message."""
    return async_redact_data(msg, SYNC_MSG_TO_REDACT)
