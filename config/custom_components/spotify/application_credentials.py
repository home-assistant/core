# noqa: ignore=all

"""Application credentials platform for spotify."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession
import logging

_logsi: SISession = SIAuto.Si.GetSession(__name__)
if _logsi == None:
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """
    Return authorization server.
    """
    # create a new authorization server instance for Spotify Web API usage.
    auth_server: AuthorizationServer = AuthorizationServer(
        authorize_url="https://accounts.spotify.com/authorize",
        token_url="https://accounts.spotify.com/api/token",
    )

    _logsi.LogObject(
        SILevel.Verbose, "Component AuthorizationServer object", auth_server
    )
    return auth_server
