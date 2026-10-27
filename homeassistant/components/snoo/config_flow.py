"""Config flow for the Happiest Baby Snoo integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import jwt
import probatio
from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException
from python_snoo.snoo import Snoo

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class SnooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Happiest Baby Snoo."""

    VERSION = 1

    async def _async_validate_credentials(
        self, username: str, password: str
    ) -> tuple[str | None, dict[str, str]]:
        """Validate the credentials and return the user uuid and errors."""
        hub = Snoo(
            email=username,
            password=password,
            clientsession=async_get_clientsession(self.hass),
        )
        try:
            tokens = await hub.authorize()
        except SnooAuthException:
            return None, {"base": "cannot_connect"}
        except InvalidSnooAuth:
            return None, {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        # Authorizing starts a token refresh task that only disconnect cancels
        await hub.disconnect()
        user_uuid: str = jwt.decode(
            tokens.aws_access, options={"verify_signature": False}
        )["username"]
        return user_uuid, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_uuid, errors = await self._async_validate_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if user_uuid is not None:
                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]
        if user_input is not None:
            user_uuid, errors = await self._async_validate_credentials(
                username, user_input[CONF_PASSWORD]
            )
            if user_uuid is not None:
                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_USERNAME: username},
            errors=errors,
        )
