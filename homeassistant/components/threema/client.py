"""Threema Gateway API client, wired to Home Assistant's shared aiohttp session."""

from aiothreema import (
    ThreemaAuthError,
    ThreemaConnectionError,
    ThreemaGatewayClient,
    ThreemaSendError,
    derive_public_key,
    generate_key_pair,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

__all__ = [
    "ThreemaAPIClient",
    "ThreemaAuthError",
    "ThreemaConnectionError",
    "ThreemaSendError",
    "derive_public_key",
    "generate_key_pair",
]


class ThreemaAPIClient(ThreemaGatewayClient):
    """Threema Gateway client bound to Home Assistant's shared aiohttp session.

    The Gateway HTTP protocol and end-to-end encryption live in the
    `aiothreema` library; this class only wires it up to Home Assistant.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        gateway_id: str,
        api_secret: str,
        private_key: str | None = None,
    ) -> None:
        """Initialize the client with Home Assistant's shared session."""
        super().__init__(
            gateway_id,
            api_secret,
            private_key,
            session=async_get_clientsession(hass),
        )
