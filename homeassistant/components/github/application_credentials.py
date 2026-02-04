"""Application credentials platform for GitHub."""

from aiogithubapi.const import (
    BASE_GITHUB_URL,
    OAUTH_ACCESS_TOKEN_PATH,
    OAUTH_DEVICE_LOGIN_PATH,
)

from homeassistant.components.application_credentials import (
    DeviceFlowAuthorizationServer,
)
from homeassistant.core import HomeAssistant


async def async_get_device_flow_authorization_server(
    hass: HomeAssistant,
) -> DeviceFlowAuthorizationServer:
    """Return authorization server."""
    return DeviceFlowAuthorizationServer(
        authorize_url=BASE_GITHUB_URL + OAUTH_DEVICE_LOGIN_PATH,
        token_url=BASE_GITHUB_URL + OAUTH_ACCESS_TOKEN_PATH,
    )
