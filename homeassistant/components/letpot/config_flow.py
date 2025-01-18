"""Config flow for the LetPot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from letpot.client import LetPotClient
from letpot.exceptions import LetPotAuthenticationException, LetPotConnectionException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            ),
        ),
    }
)
STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
    }
)


class LetPotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LetPot."""

    VERSION = 1

    async def _async_validate_credentials(
        self, email: str, password: str
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Try logging in to the LetPot account and returns credential info."""
        websession = async_get_clientsession(self.hass)
        client = LetPotClient(websession)
        try:
            auth = await client.login(email, password)
        except LetPotConnectionException:
            return {"base": "cannot_connect"}, None
        except LetPotAuthenticationException:
            return {"base": "invalid_auth"}, None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}, None
        else:
            return {}, {
                CONF_ACCESS_TOKEN: auth.access_token,
                CONF_ACCESS_TOKEN_EXPIRES: auth.access_token_expires,
                CONF_REFRESH_TOKEN: auth.refresh_token,
                CONF_REFRESH_TOKEN_EXPIRES: auth.refresh_token_expires,
                CONF_USER_ID: auth.user_id,
                CONF_EMAIL: auth.email,
            }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, data_dict = await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors and data_dict is not None:
                await self.async_set_unique_id(data_dict[CONF_USER_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=data_dict[CONF_EMAIL], data=data_dict
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors, data_dict = await self._async_validate_credentials(
                reauth_entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors and data_dict is not None:
                await self.async_set_unique_id(data_dict[CONF_USER_ID])
                if reauth_entry.unique_id != data_dict[CONF_USER_ID]:
                    # Abort if the received account is different and already added
                    self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=self.unique_id,
                    data_updates=data_dict,
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"email": reauth_entry.title},
            errors=errors,
        )
