"""Adds config flow for wsdot."""

from asyncio import timeout
import logging
from typing import Any
from urllib.parse import urlencode, urlunsplit

from aiohttp.client_exceptions import (
    ClientConnectorError,
    ClientError,
    ContentTypeError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_TRAVEL_TIME_ID,
    ATTR_TRAVEL_TIME_NAME,
    CONF_API_KEY,
    CONF_TRAVEL_TIMES,
    CONF_TRAVEL_TIMES_ID,
    CONF_TRAVEL_TIMES_NAME,
    DIALOG_API_KEY,
    DIALOG_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class InvalidApiKeyError(ClientError):
    """Exception indicating the user entered an invalid API Key."""

class WSDOTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for WSDOT."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                travel_time_routes = await self._get_travel_times(user_input[DIALOG_API_KEY])
            except InvalidApiKeyError:
                errors[DIALOG_API_KEY] = "Invalid API Key. If you do not have an API Key, you can get a new one at https://wsdot.wa.gov/traffic/api/"
            except (ClientConnectorError, TimeoutError, ClientError):
                err_msg = "Unable to retrieve routes from WSDOT"
                _LOGGER.exception(err_msg)
                errors["base"] = err_msg
            else:
                return self.async_create_entry(
                    title=user_input[DIALOG_NAME],
                    data={
                        CONF_API_KEY: user_input[DIALOG_API_KEY],
                        CONF_TRAVEL_TIMES: [{CONF_TRAVEL_TIMES_ID:i, CONF_TRAVEL_TIMES_NAME:n} for i, n in travel_time_routes.items()],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema({
                vol.Required(DIALOG_API_KEY): str,
                vol.Optional(DIALOG_NAME, default=DOMAIN): str,
            }),
            errors=errors,
        )

    async def _fetch_wsdot(self, api_key: str) -> dict[str, Any]:
        url = urlunsplit((
            'https',
            'wsdot.com',
            '/Traffic/api/TravelTimes/TravelTimesREST.svc/GetTravelTimesAsJson',
            urlencode({"AccessCode": api_key}),
            ''
        ))
        session = async_get_clientsession(self.hass)

        async with timeout(15):
            _LOGGER.debug("Querying WSDOT [GET] %s", url)
            async with session.get(url) as response:
                try:
                    j = await response.json()
                except ContentTypeError as cte:
                    _LOGGER.warning("WSDOT did not respond with JSON. This indicates that an (HTML) error page was returned")
                    raise InvalidApiKeyError from cte
                except Exception:
                    _LOGGER.warning("Unexpected response from WSDOT", exc_info=True)
                    raise
                else:
                    _LOGGER.debug("WSDOT responded %s", j)
                return j

    async def _get_travel_times(self, api_key: str) -> dict[str, str]:
        travel_times_blobs = await self._fetch_wsdot(api_key)
        return {str(tt[ATTR_TRAVEL_TIME_ID]): tt[ATTR_TRAVEL_TIME_NAME] for tt in travel_times_blobs}
