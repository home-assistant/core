"""Helpers for the Linksys Smart Wi-Fi integration."""

from collections.abc import Mapping
from typing import Any

from jnap import JNAPClient

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


def build_client(hass: HomeAssistant, data: Mapping[str, Any]) -> JNAPClient:
    """Construct a JNAPClient from config entry or config flow data."""
    kwargs: dict[str, Any] = {}
    if username := data.get(CONF_USERNAME):
        kwargs["username"] = username
    return JNAPClient(
        data[CONF_HOST],
        async_get_clientsession(hass),
        data.get(CONF_PASSWORD),
        **kwargs,
    )
