import json  # noqa: D100

import requests
from trest_solar_service import TrestIdentityService

from homeassistant.core import HomeAssistant


class CloudSolarTrestService:
    """The class representing the Api of the Cloud Solar Trest application."""

    def __init__(self) -> None:
        """Init the class."""
        self.base_url = "https://cloud.solar.trest.se:443"
        self.trest_identity_service = TrestIdentityService()

    def get_latest_solar_history(self, hass: HomeAssistant) -> str:
        """Get the latest solar histoy from the Api."""
        self.trest_identity_service.renew_token(hass)

        headers = {"X-Token": self.trest_identity_service.token}
        response = requests.get(
            self.base_url + "/api/v1/solar/getlatesthistory", headers=headers, timeout=3
        )

        return json.loads(response.text)
