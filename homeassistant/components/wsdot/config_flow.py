"""Adds config flow for wsdot."""

from asyncio import timeout
from typing import Any
from urllib.parse import urlencode, urlunsplit

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_USER
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = "wsdot"
CONF_NAME = "Name"
CONF_API_KEY = "API Key"


class WSDOTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for WSDOT"""
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}

        if user_input is not None:
            try:
                travel_time_routes = await self.get_travel_times(user_input[CONF_API_KEY])
            except (ClientConnectorError, TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            #except InvalidApiKeyError:
                #errors[CONF_API_KEY] = "invalid_api_key"
            else:
                await self.async_set_unique_id(
                    "+".join(travel_time_routes.keys()),
                    raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        "api_key": user_input[CONF_API_KEY],
                        "travel_time": [{"id":i, "name":n} for i, n in travel_time_routes.items()],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=DOMAIN): str,
            }),
            errors=errors,
        )

    async def fetch_wsdot(self, api_key: str) -> dict[str, Any]:
        url = urlunsplit((
            'https',
            'wsdot.com',
            '/Traffic/api/TravelTimes/TravelTimesREST.svc/GetTravelTimesAsJson',
            urlencode({"AccessCode": api_key}),
            ''
        ))
        session = async_get_clientsession(self.hass)

        async with timeout(15):
            async with session.get(url) as response:
                return await response.json()

    async def get_travel_times(self, api_key: str) -> dict[str, str]:
        travel_times_blobs = await self.fetch_wsdot(api_key)
        return {str(tt["TravelTimeID"]): tt["Name"] for tt in travel_times_blobs}