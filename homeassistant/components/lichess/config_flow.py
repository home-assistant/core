"""Config flow for the Lichess integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiolichess import AioLichess
from aiolichess.exceptions import AioLichessError, AuthError
from aiolichess.models import LichessUser
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, TOKEN_URL

_LOGGER = logging.getLogger(__name__)

STEP_SCHEMA = probatio.Schema({probatio.Required(probatio.Secret(CONF_API_TOKEN)): str})


class LichessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lichess."""

    async def _async_validate_token(
        self, token: str
    ) -> tuple[LichessUser | None, dict[str, str]]:
        """Validate the API token and return the user or the errors."""
        client = AioLichess(session=async_get_clientsession(self.hass))
        try:
            user = await client.get_all(token=token)
        except AuthError:
            return None, {"base": "invalid_auth"}
        except AioLichessError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        return user, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user, errors = await self._async_validate_token(user_input[CONF_API_TOKEN])
            if user is not None:
                await self.async_set_unique_id(user.id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user.username, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            description_placeholders={"token_url": TOKEN_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API token."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user, errors = await self._async_validate_token(user_input[CONF_API_TOKEN])
            if user is not None:
                await self.async_set_unique_id(user.id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_SCHEMA,
            description_placeholders={
                "username": reauth_entry.title,
                "token_url": TOKEN_URL,
            },
            errors=errors,
        )
