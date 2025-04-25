"""Config flow for the Victron VRM Solar Forecast integration."""

from __future__ import annotations

import logging
from typing import Any

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models import Site
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_API_KEY, CONF_SITE_ID, DOMAIN
from .coordinator import jwt_regex
from .errors import CannotConnect, InvalidAuth, SiteNotFound

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_SITE_ID): int,
    }
)


class VRMClientHolder:
    """Holds the VRM client. Mainly for test patches."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the VRM client holder."""
        self.client = VictronVRMClient(
            token=api_key,
            token_type="Bearer" if jwt_regex.match(api_key) else "Token",
            client_session=get_async_client(hass),
        )

    async def get_site(self, site_id: int) -> Site | None:
        """Get the site data."""
        return await self.client.users.get_site(site_id)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    client = VRMClientHolder(hass, data[CONF_API_KEY])
    try:
        site_data = await client.get_site(data[CONF_SITE_ID])
    except AuthenticationError as err:
        raise InvalidAuth("Invalid authentication or permission") from err
    except VictronVRMError as err:
        if err.status_code in (401, 403):
            raise InvalidAuth("Invalid authentication or permission") from err
        raise CannotConnect(
            f"Cannot connect to site {data[CONF_SITE_ID]}. Reason: {err.message}"
        ) from err
    if site_data is None:
        raise SiteNotFound(f"Site with ID {data[CONF_SITE_ID]} not found")

    # Return info that you want to store in the config entry.
    return {"title": f"VRM Forecast for {site_data.name}", "data": data}


class VRMForecastsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron VRM Solar Forecast."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_SITE_ID: user_input[CONF_SITE_ID]})
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect as err:
                _LOGGER.warning(str(err))
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.warning(
                    "Invalid authentication/permission for %s", user_input[CONF_SITE_ID]
                )
                errors["base"] = "invalid_auth"
            except SiteNotFound:
                _LOGGER.warning("Site %s not found", user_input[CONF_SITE_ID])
                errors["base"] = "site_not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
