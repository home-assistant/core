"""Config flow for the Clicky Web Analytics integration."""

from typing import Any, override

from aiohttp import ClientError
import probatio
from pyclicky import (
    AuthenticationError,
    ClickyAPIError,
    ClickyClient,
    ConnectionError,
    InvalidEndpoint,
    ServiceUnavailable,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SITE_ID): TextSelector(),
        probatio.Required(CONF_SITEKEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class ClickyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Clicky Web Analytics."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (website name and API credentials)."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_SITE_ID: user_input[CONF_SITE_ID]})

            client = ClickyClient(
                site_id=user_input[CONF_SITE_ID],
                sitekey=user_input[CONF_SITEKEY],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.visitors_online()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (
                ConnectionError,
                InvalidEndpoint,
                ServiceUnavailable,
                ClientError,
                TimeoutError,
            ):
                errors["base"] = "cannot_connect"
            except ClickyAPIError as error:
                errors["base"] = "api_error"
                description_placeholders["error"] = str(error)
            else:
                return self.async_create_entry(
                    title=user_input[CONF_SITE_ID], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
