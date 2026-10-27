"""Tests for Beatbot application credentials."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.beatbot.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.core import HomeAssistant


async def test_auth_implementation(hass: HomeAssistant) -> None:
    """Create a PKCE implementation with the required scope."""
    implementation = await async_get_auth_implementation(
        hass,
        "beatbot",
        ClientCredential("client-id", "client-secret", name="Beatbot"),
    )

    assert implementation.client_id == "client-id"
    assert implementation.client_secret == "client-secret"
    assert implementation.extra_authorize_data["scope"] == "device:info"
