"""Sutro API library."""
from typing import Any

import requests

from homeassistant.core import HomeAssistant


class SutroApi:
    """Sutro API."""

    def __init__(self, hass: HomeAssistant, api_token: str) -> None:
        """Initialize."""
        self.hass = hass
        self.api_token = api_token

    def get_info(self) -> dict[str, Any]:
        """Get info about user and device."""
        query = """
        {
            me {
                id
                firstName
                device {
                    batteryLevel
                    serialNumber
                    temperature
                }
                pool {
                    latestReading {
                        alkalinity
                        chlorine
                        ph
                        readingTime
                    }
                }
            }
        }
        """

        response = requests.post(
            "https://api.mysutro.com/graphql",
            data=query,
            headers={"Authorization": f"Bearer {self.api_token}"},
        )

        return response.json()

    async def async_get_info(self) -> dict[str, Any]:
        """Asynchronously get info about user and device."""
        return await self.hass.async_add_executor_job(self.get_info)
