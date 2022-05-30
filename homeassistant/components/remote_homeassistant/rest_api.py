"""Simple implementation to call Home Assistant REST API."""

from homeassistant import exceptions
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_URL = "{proto}://{host}:{port}/api/remote_homeassistant/discovery"


class ApiProblem(exceptions.HomeAssistantError):
    """Error to indicate problem reaching API."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BadResponse(exceptions.HomeAssistantError):
    """Error to indicate a bad response was received."""


class UnsupportedVersion(exceptions.HomeAssistantError):
    """Error to indicate an unsupported version of Home Assistant."""


class EndpointMissing(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def async_get_discovery_info(hass, host, port, secure, access_token, verify_ssl):
    """Get discovery information from server."""
    url = API_URL.format(
        proto="https" if secure else "http",
        host=host,
        port=port,
    )
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
    }
    session = async_get_clientsession(hass, verify_ssl)

    # Fetch discovery info location for name and unique UUID
    async with session.get(url, headers=headers) as resp:
        if resp.status == 404:
            raise EndpointMissing()
        if 400 <= resp.status < 500:
            raise InvalidAuth()
        if resp.status != 200:
            raise ApiProblem()
        json = await resp.json()
        if not isinstance(json, dict):
            raise BadResponse(f"Bad response data: {json}")
        if "uuid" not in json:
            raise UnsupportedVersion()
        return json
