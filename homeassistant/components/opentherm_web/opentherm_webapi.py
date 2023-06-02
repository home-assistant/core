"""WebApi Poller for OpenThermWeb."""
from __future__ import annotations

import urllib.parse

import requests
from requests import Response

from homeassistant.core import HomeAssistant

from .const import TIMEOUT


class OpenThermWebApi:
    """Class to communicate with OpenTherm Webapi."""

    def __init__(self, hass: HomeAssistant, host: str, secret: str) -> None:
        """Initialize."""
        self.hass = hass
        self.host = host
        self.secret = secret

    async def authenticate(self) -> bool:
        """Test connection."""

        token = await self.hass.async_add_executor_job(self.get_token)
        if token:
            return True

        return False

    def get_token(self) -> str:
        """Get bearer token."""
        api_url = urllib.parse.urljoin(self.host, "/connect/token")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = {
            "grant_type": "client_credentials",
            "scope": "OpenThermAPI",
        }

        response = requests.post(
            api_url,
            data=data,
            headers=headers,
            auth=("WebApi", self.secret),
            timeout=TIMEOUT,
        ).json()

        return response.get("access_token")

    def get_controller(self) -> OpenThermController:
        """Retrieve controller."""
        token = self.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        api_url = urllib.parse.urljoin(self.host, "/opentherm/controller")
        response = requests.get(api_url, headers=headers, timeout=TIMEOUT)

        return OpenThermController(response)


class OpenThermController:
    """Class that represents the data object that holds the data."""

    def __init__(self, response: Response) -> None:
        """Initiatlize."""
        json = response.json()
        self.device_id = json.get("deviceId")
        self.poller = json.get("poller")
