import json  # noqa: D100

import aiohttp  # noqa: D100

from homeassistant.core import HomeAssistant

from .trest_identity_service import TrestIdentityService


class CloudSolarTrestService:
    """The class representing the Api of the Cloud Solar Trest application."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Init the class."""
        self.base_url = "https://cloud.solar.trest.se:443"
        self.trest_identity_service = TrestIdentityService(hass, username, password)

    async def get_latest_solar_history_async(self) -> str:
        """Get the latest solar histoy from the Api."""
        await self.trest_identity_service.renew_token_async()

        headers = {"X-Token": self.trest_identity_service.token}

        async with aiohttp.ClientSession() as session, session.get(
            self.base_url + "/api/v1/solar/getlatesthistory",
            headers=headers,
            timeout=3,
        ) as response:
            response_text = await response.text()

            return json.loads(response_text)
