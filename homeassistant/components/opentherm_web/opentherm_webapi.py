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

        return OpenThermController(self, response)

    def push_change(self, controller: OpenThermController) -> None:
        """Push controller."""
        token = self.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        api_url = urllib.parse.urljoin(self.host, "/opentherm/controller")
        data = {
            "deviceId": controller.device_id,
            "enabled": controller.enabled,
            "roomSetpoint": controller.room_setpoint,
            "dhwSetpoint": controller.dhw_setpoint,
            "away": controller.away,
        }
        requests.put(api_url, headers=headers, json=data, timeout=TIMEOUT)


class OpenThermController:
    """Class that represents the data object that holds the data."""

    web_api: OpenThermWebApi

    def __init__(self, web_api: OpenThermWebApi, response: Response) -> None:
        """Initiatlize."""
        self.web_api = web_api
        json = response.json()
        self.device_id = json.get("deviceId")
        self.dhw_setpoint = json.get("dhwSetpoint")
        self.chw_setpoint = json.get("chwSetpoint")
        self.room_setpoint = json.get("roomSetpoint")
        self.away = json.get("away")
        self.enabled = json.get("enabled")
        self.chw_temperature = json.get("chwTemperature")
        self.dhw_temperature = json.get("dhwTemperature")
        self.room_temperature = json.get("roomTemperature")
        self.outside_temperature = json.get("outsideTemperature")
        self.chw_active = json.get("chwActive")
        self.dhw_active = json.get("dhwActive")

    def set_room_temperature(self, temperature: float) -> None:
        """Set room temperature."""
        self.room_setpoint = temperature
        self.web_api.push_change(self)

    def set_dhw_temperature(self, temperature: float) -> None:
        """Set domestic hot water temperature."""
        self.dhw_setpoint = temperature
        self.web_api.push_change(self)

    def set_away_mode(self, away_mode: bool) -> None:
        """Set away mode."""
        self.away = away_mode
        self.web_api.push_change(self)

    def set_hvac_mode(self, enabled: bool) -> None:
        """Set HVAC mode."""
        self.enabled = enabled
        self.web_api.push_change(self)
