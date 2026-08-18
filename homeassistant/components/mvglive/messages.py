"""Fetch incident messages from the MVG API.

The upstream ``mvg`` package (https://pypi.org/project/mvg/) dropped the
``/messages`` endpoint after version 1.1.x, so this integration keeps a
minimal client for it here.
"""

from typing import Any, cast

import aiohttp
from mvg import MvgApiError, TransportType

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

MESSAGES_URL = "https://www.mvg.de/api/bgw-pt/v3/messages"

UNKNOWN_TRANSPORT_TYPE = ("Unbekannt", "mdi:help-circle-outline")


def _transport_type_value(name: str) -> tuple[str, str]:
    """Resolve a transport type name to (label, icon), falling back for unknown types."""
    try:
        return cast(tuple[str, str], TransportType[name].value)
    except KeyError:
        return UNKNOWN_TRANSPORT_TYPE


async def fetch_incident_messages(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Retrieve a list of all incident messages.

    :raises MvgApiError: raised on communication failure or unexpected result
    :return: a list of incident messages as dictionary
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(MESSAGES_URL) as resp:
            if resp.status != 200:
                raise MvgApiError(
                    f"Bad API call: Got response ({resp.status}) from {MESSAGES_URL}"
                )
            if resp.content_type != "application/json":
                raise MvgApiError(
                    f"Bad API call: Got content type {resp.content_type} from {MESSAGES_URL}"
                )
            result = await resp.json()
    except aiohttp.ClientError as exc:
        raise MvgApiError(
            f"Bad API call: Got {type(exc)!s} from {MESSAGES_URL}"
        ) from exc

    try:
        assert isinstance(result, list)

        messages: list[dict[str, Any]] = []
        for message in result:
            if message.get("type") != "INCIDENT":
                continue
            messages.append(
                {
                    "title": message.get("title", "Unknown"),
                    "description": message.get(
                        "description", "No description available"
                    ),
                    "publication": int(message.get("publication", 0) / 1000),
                    "validFrom": int(message.get("validFrom", 0) / 1000),
                    "validTo": int(message.get("validTo", 0) / 1000),
                    "type": message.get("type", "Unknown"),
                    "provider": message.get("provider", "Unknown"),
                    "lines": [
                        {
                            "label": line.get("label", "Unknown"),
                            "transportType": _transport_type_value(
                                line.get("transportType", "")
                            )[0],
                            "network": line.get("network", "Unknown"),
                            "divaId": line.get("divaId", "Unknown"),
                            "sev": line.get("sev", False),
                        }
                        for line in message.get("lines", [])
                    ],
                }
            )
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        raise MvgApiError("Bad API call: Could not parse message data") from exc
    return messages
