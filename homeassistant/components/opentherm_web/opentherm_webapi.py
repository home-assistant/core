"""WebApi Poller for OpenThermWeb."""
from __future__ import annotations

import urllib.parse

from oidc_client.config import ProviderConfig
from oidc_client.lib import login


class OpenThermWebApi:
    """Class to communicate with OpenTherm Webapi."""

    def __init__(self, host: str, secret: str) -> None:
        """Initialize."""
        self.host = host
        self.secret = secret

    async def authenticate(self) -> bool:
        """Test connection."""
        response = login(
            ProviderConfig(
                self.host,
                authorization_endpoint=urllib.parse.urljoin(
                    self.host, "/connect/authorize"
                ),
                token_endpoint=urllib.parse.urljoin(self.host, "/connect/token"),
            ),
            client_id="WebApi",
            client_secret=self.secret,
            interactive=False,
        )

        if not response.access_token:
            return False

        return True


class OpenThermController:
    """Class that represents the data object that holds the data."""

    def __init__(self) -> None:
        """Initiatlize."""
