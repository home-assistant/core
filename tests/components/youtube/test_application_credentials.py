"""Test Application Credentails."""
from homeassistant.components.youtube.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.core import HomeAssistant


async def test_placeholders(hass: HomeAssistant):
    """Test Application Credentails placeholders."""
    assert await async_get_description_placeholders(hass) == {
        "oauth_consent_url": "https://console.cloud.google.com/apis/credentials/consent",
        "more_info_url": "https://www.home-assistant.io/integrations/youtube/",
        "oauth_creds_url": "https://console.cloud.google.com/apis/credentials",
    }
