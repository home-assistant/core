"""Fing API library."""

import httpx

try:
    from models import ContactResponse, DeviceResponse
except ImportError:
    from .models import ContactResponse, DeviceResponse


class Fing:
    """Fing API library."""

    def __init__(self, ip: str, port: int, key: str) -> None:
        """Initialize Fing API object."""
        self._host = f"http://{ip}:{port}/1"
        self._key = key

    async def get_devices(self, timeout: float = 120) -> DeviceResponse:
        """Return devices discovered by Fing."""
        url = f"{self._host}/devices?auth={self._key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
        return DeviceResponse(response.raise_for_status().json())

    async def get_contacts(self, timeout: float = 120) -> ContactResponse:
        """Return information about Fing contacts."""
        url = f"{self._host}/people?auth={self._key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
        return ContactResponse(response.raise_for_status().json())
