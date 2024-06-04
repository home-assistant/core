"""Helpers to redact Google Assistant data when logging."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.redact import REDACTED, async_redact_data, partial_redact

GOOGLE_MSG_TO_REDACT: dict[str, Callable[[str], str]] = {
    "agentUserId": partial_redact,
    "uuid": partial_redact,
    "webhookId": partial_redact,
}

MDNS_TXT_TO_REDACT = [
    "location_name",
    "uuid",
    "external_url",
    "internal_url",
    "base_url",
]


def partial_redact_list_item(x: list[str], to_redact: list[str]) -> list[str]:
    """Redact only specified string in a list of strings."""
    if not isinstance(x, list):
        return x
    result = []
    for itm in x:
        if not isinstance(itm, str):
            result.append(itm)
            continue
        for pattern in to_redact:
            if itm.startswith(pattern):
                result.append(f"{pattern}={REDACTED}")
                break
        else:
            result.append(itm)
    return result


def partial_redact_txt_list(x: list[str]) -> list[str]:
    """Redact strings from home-assistant mDNS txt records."""
    return partial_redact_list_item(x, MDNS_TXT_TO_REDACT)


def partial_redact_txt_dict(x: dict[str, str]) -> dict[str, str]:
    """Redact strings from home-assistant mDNS txt records."""
    if not isinstance(x, dict):
        return x
    result = {}
    for k, v in x.items():
        result[k] = REDACTED if k in MDNS_TXT_TO_REDACT else v
    return result


def partial_redact_string(x: str, to_redact: str) -> str:
    """Redact only a specified string."""
    if x == to_redact:
        return partial_redact(x)
    return x


@callback
def async_redact_msg(msg: dict[str, Any], agent_user_id: str) -> dict[str, Any]:
    """Mask sensitive data in message."""
    return async_redact_data(
        msg,
        GOOGLE_MSG_TO_REDACT
        | {
            "data": partial_redact_txt_list,
            "id": partial(partial_redact_string, to_redact=agent_user_id),
            "texts": partial_redact_txt_list,
            "txt": partial_redact_txt_dict,
        },
    )
