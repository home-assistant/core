"""Utility functions for the AEMET OpenData integration."""

import base64
import binascii
from datetime import UTC, datetime
import json
from typing import Any

from aemet_opendata.exceptions import AemetError, AuthError
from aemet_opendata.interface import AEMET, ConnectionOptions
import probatio

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

API_KEY_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


def get_api_key_expiration(api_key: str) -> datetime | None:
    """Return the expiration date from an AEMET API key JWT."""
    try:
        _, payload_segment, _ = api_key.split(".", 2)
        payload_segment += "=" * (-len(payload_segment) % 4)
        payload: Any = json.loads(base64.urlsafe_b64decode(payload_segment))
    except binascii.Error, json.JSONDecodeError, TypeError, ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    expiration = payload.get("exp")
    if not isinstance(expiration, (int, float)) or isinstance(expiration, bool):
        return None

    try:
        return datetime.fromtimestamp(expiration, tz=UTC)
    except OSError, OverflowError, ValueError:
        return None


async def async_validate_api_key(
    hass: HomeAssistant,
    api_key: str,
    latitude: float,
    longitude: float,
) -> str | None:
    """Validate an API key by querying AEMET for the given coordinates."""
    options = ConnectionOptions(api_key)
    aemet = AEMET(aiohttp_client.async_get_clientsession(hass), options)
    try:
        await aemet.select_coordinates(latitude, longitude)
    except AuthError:
        return "invalid_api_key"
    except AemetError:
        return "cannot_connect"
    return None
