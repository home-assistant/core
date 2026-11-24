"""Config flow for the NEPViewer integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import aiohttp
from aionepviewer import NepAuthError, NepConnectionError, NepViewer
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class NEPViewerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NEPViewer."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = await self._async_login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if uid is not None:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            uid = await self._async_login(
                reauth_entry.data[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if uid is not None:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
        )

    async def _async_login(
        self, email: str, password: str, errors: dict[str, str]
    ) -> str | None:
        """Log in and return the account ID, or None after filling errors."""
        client = NepViewer(async_get_clientsession(self.hass), email, password)
        try:
            uid = (await client.authenticate()).user_info.uid
        except NepAuthError:
            errors["base"] = "invalid_auth"
        except NepConnectionError, aiohttp.ClientError, TimeoutError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception while logging in")
            errors["base"] = "unknown"
        else:
            return uid
        return None
