"""Config flow for the Cync integration."""

from __future__ import annotations

import logging
from typing import Any

from pycync import Auth
from pycync.exceptions import AuthFailedError, CyncError, TwoFactorRequiredError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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


class CyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cync."""

    VERSION = 1

    cync_auth: Auth

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt login with user credentials."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

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

    async def _create_config_entry(self, user_email: str) -> ConfigFlowResult:
        """Create the Cync config entry using input user data."""

        cync_user = self.cync_auth.user
        await self.async_set_unique_id(str(cync_user.user_id))
        self._abort_if_unique_id_configured()

        config = {
            CONF_USER_ID: cync_user.user_id,
            CONF_AUTHORIZE_STRING: cync_user.authorize,
            CONF_EXPIRES_AT: cync_user.expires_at,
            CONF_ACCESS_TOKEN: cync_user.access_token,
            CONF_REFRESH_TOKEN: cync_user.refresh_token,
        }
        return self.async_create_entry(title=user_email, data=config)
