"""Config flow for the Cync integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pycync import Auth
from pycync.exceptions import AuthFailedError, CyncError, TwoFactorRequiredError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TWO_FACTOR_CODE,
    CONF_USER_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_TWO_FACTOR_SCHEMA = vol.Schema({vol.Required(CONF_TWO_FACTOR_CODE): str})

STEP_REAUTH_CONFIRM_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class CyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cync."""

    VERSION = 1

    cync_auth: Auth

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt login with user credentials."""
        errors: dict[str, str] = {}

        if user_input:
            self.cync_auth = Auth(
                async_get_clientsession(self.hass),
                username=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await self.cync_auth.login()
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except TwoFactorRequiredError:
                return await self.async_step_two_factor()
            except CyncError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._create_config_entry(self.cync_auth.username)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_two_factor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt login with the two factor auth code sent to the user."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="two_factor", data_schema=STEP_TWO_FACTOR_SCHEMA, errors=errors
            )
        try:
            await self.cync_auth.login(user_input[CONF_TWO_FACTOR_CODE])
        except AuthFailedError:
            errors["base"] = "invalid_auth"
        except CyncError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self._create_config_entry(self.cync_auth.username)

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
        """Dialog that informs the user that reauth is required and prompts for their password."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input:
            self.cync_auth = Auth(
                async_get_clientsession(self.hass),
                username=reauth_entry.title,
                password=user_input[CONF_PASSWORD],
            )
            try:
                await self.cync_auth.login()
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except TwoFactorRequiredError:
                return await self.async_step_two_factor()
            except CyncError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._create_config_entry(self.cync_auth.username)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_CONFIRM_SCHEMA,
            errors=errors,
            description_placeholders={CONF_EMAIL: reauth_entry.title},
        )

    async def _create_config_entry(self, user_email: str) -> ConfigFlowResult:
        """Create the Cync config entry using input user data."""

        cync_user = self.cync_auth.user
        await self.async_set_unique_id(str(cync_user.user_id))

        config_data = {
            CONF_USER_ID: cync_user.user_id,
            CONF_AUTHORIZE_STRING: cync_user.authorize,
            CONF_EXPIRES_AT: cync_user.expires_at,
            CONF_ACCESS_TOKEN: cync_user.access_token,
            CONF_REFRESH_TOKEN: cync_user.refresh_token,
        }

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=config_data
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_email, data=config_data)
