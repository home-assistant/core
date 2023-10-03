"""application_credentials platform for Google Assistant SDK."""
from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """
    Return authorization server.

    This function returns an instance of the AuthorizationServer class, which represents
    an authorization server for the Google Assistant SDK.

    Parameters:
        hass (HomeAssistant): The Home Assistant instance.

    Returns:
        AuthorizationServer: An instance of the AuthorizationServer class.
    """
    return AuthorizationServer(
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """
    Return description placeholders for the credentials dialog.

    This function returns a dictionary of description placeholders that can be
    used in the credentials dialog for the Google Assistant SDK.

    Parameters:
        hass (HomeAssistant): The Home Assistant instance.

    Returns:
        dict[str, str]: A dictionary of description placeholders.
    """
    return {
        "oauth_consent_url": (
            "https://console.cloud.google.com/apis/credentials/consent"
        ),
        "more_info_url": (
            "https://www.home-assistant.io/integrations/google_assistant_sdk/"
        ),
        "oauth_creds_url": "https://console.cloud.google.com/apis/credentials",
    }
