"""WebApi Poller for OpenThermWeb."""
from __future__ import annotations

import urllib.parse

import requests

from .const import TIMEOUT
from .opentherm_controller import OpenThermController


class OpenThermWebApi:
    """Class to communicate with OpenTherm Webapi."""

    controller: OpenThermController

    def __init__(self, host: str, secret: str) -> None:
        """Initialize."""
        self.host = host
        self.secret = secret

    def authenticate(self) -> bool:
        """Test connection."""

        token = self.get_token()
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
        """Get controller."""
        return self.controller

    def refresh_controller(self) -> OpenThermController:
        """Retrieve controller."""
        token = self.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        api_url = urllib.parse.urljoin(self.host, "/opentherm/controller")
        response = requests.get(api_url, headers=headers, timeout=TIMEOUT)
        self.controller = OpenThermController(response)
        return self.controller

    def push_change(self) -> None:
        """Push controller."""
        token = self.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        api_url = urllib.parse.urljoin(self.host, "/opentherm/controller")
        data = self.controller.get_json()
        requests.put(api_url, headers=headers, json=data, timeout=TIMEOUT)

    def set_room_temperature(self, temperature: float) -> None:
        """Set room temperature."""
        self.controller.room_setpoint = temperature
        self.push_change()

    def set_dhw_temperature(self, temperature: float) -> None:
        """Set domestic hot water temperature."""
        self.controller.dhw_setpoint = temperature
        self.push_change()

    def set_dhw_away_mode(self, away_mode: bool) -> None:
        """Set away mode."""
        self.controller.dhw_away = away_mode
        self.push_change()

    def set_hvac_mode(self, enabled: bool) -> None:
        """Set HVAC mode."""
        self.controller.chw_away = not enabled
        self.push_change()
