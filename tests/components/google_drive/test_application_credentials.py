"""Test the Google Drive application_credentials."""

import pytest

from homeassistant import setup
from homeassistant.components.google_drive.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("additional_components", "external_url", "expected_redirect_uri"),
    [
        ([], "https://example.com", "https://example.com/auth/external/callback"),
        ([], None, "https://YOUR_DOMAIN:PORT/auth/external/callback"),
        (["my"], "https://example.com", "https://my.home-assistant.io/redirect/oauth"),
    ],
)
async def test_description_placeholders(
    hass: HomeAssistant,
    additional_components: list[str],
    external_url: str | None,
    expected_redirect_uri: str,
) -> None:
    """Test description placeholders."""
    for component in additional_components:
        assert await setup.async_setup_component(hass, component, {})
    hass.config.external_url = external_url
    placeholders = await async_get_description_placeholders(hass)
    assert placeholders == {
        "oauth_consent_url": "https://console.cloud.google.com/apis/credentials/consent",
        "more_info_url": "https://www.home-assistant.io/integrations/google_drive/",
        "oauth_creds_url": "https://console.cloud.google.com/apis/credentials",
        "redirect_url": expected_redirect_uri,
    }
