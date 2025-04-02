"""KAT Bulgaria Client Wrapper."""

import logging

import httpx

from homeassistant.core import HomeAssistant

from .models import UnraidData

_LOGGER = logging.getLogger(__name__)


class UnraidClient:
    """KAT Client Manager."""

    unraid_host: str
    unraid_apikey: str

    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, host: str, apikey: str) -> None:
        """Initialize client."""
        super().__init__()

        self.unraid_host = host
        self.unraid_apikey = apikey

        self.hass = hass

    # async def __graphql(self, endpoint: str, query: str, variables: dict) -> UnraidData:
    async def __graphql(self, endpoint: str, query: str) -> UnraidData:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                endpoint,
                json={"query": query},
                # json={"query": query, "variables": variables or {}},
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.unraid_apikey,
                },
            )
            response.raise_for_status()
            json_data = response.json()

            return UnraidData(json_data)

    async def query_data(self) -> UnraidData:
        """Query the data."""

        endpoint = f"https://{self.unraid_host}/graphql"
        query = """
        query {
            info {
                os {
                    platform
                    distro
                    release
                    uptime
                }
                cpu {
                    manufacturer
                    brand
                    cores
                    threads
                }
            }
            array {
                state
                capacity {
                    disks {
                        free
                        used
                        total
                    }
                }
                disks {
                    name
                    size
                    status
                    temp
                }
            }
        }
        """

        return await self.__graphql(endpoint, query)
