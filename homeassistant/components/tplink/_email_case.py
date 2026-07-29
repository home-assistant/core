"""Look up a TP-Link account's canonical e-mail capitalisation.

KLAP/AES local authentication hashes the username (e-mail) case-sensitively,
but TP-Link cloud login is case-insensitive. Devices are provisioned by the
cloud with the account's *registered* e-mail case, so users who enter a
different case (their credentials still work in the Kasa app, which is
cloud-based) hit a confusing local ``AuthenticationError``.

On auth failure the config flow can call the cloud with the same credentials
(cloud login is case-insensitive, so it succeeds) and read back the canonical
e-mail, then suggest the correct capitalisation to the user.
"""

import asyncio
import logging
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

_CLOUD_URL = "https://wap.tplinkcloud.com"
_TIMEOUT = 15


async def async_get_canonical_username(
    hass: HomeAssistant, username: str, password: str
) -> str | None:
    """Return the account's canonical (registered-case) e-mail, or None.

    Never raises: any failure (wrong password, MFA/2FA, network error,
    unexpected payload) returns None so the caller falls back to the normal
    error handling.
    """
    session = async_get_clientsession(hass)
    payload = {
        "method": "login",
        "params": {
            "appType": "Kasa_Android",
            "cloudUserName": username,
            "cloudPassword": password,
            "terminalUUID": str(uuid.uuid4()),
        },
    }
    try:
        async with asyncio.timeout(_TIMEOUT):
            resp = await session.post(_CLOUD_URL, json=payload)
            data = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("TP-Link cloud e-mail-case lookup failed: %s", err)
        return None

    if not isinstance(data, dict) or data.get("error_code") != 0:
        _LOGGER.debug(
            "TP-Link cloud e-mail-case lookup returned error_code %s",
            data.get("error_code") if isinstance(data, dict) else "?",
        )
        return None

    result = data.get("result")
    if isinstance(result, dict):
        email = result.get("email")
        if isinstance(email, str):
            return email
    return None


def suggest_username_case(entered: str, canonical: str | None) -> str | None:
    """Return the canonical username if it differs from ``entered`` only in case.

    Returns None when there is nothing useful to suggest (no canonical value,
    identical strings, or a genuinely different address).
    """
    if (
        canonical
        and canonical != entered
        and canonical.casefold() == entered.casefold()
    ):
        return canonical
    return None
