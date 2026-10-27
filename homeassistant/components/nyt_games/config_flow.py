"""Config flow for NYT Games."""

from collections.abc import Mapping
from typing import Any, override

from nyt_games import NYTGamesAuthenticationError, NYTGamesClient, NYTGamesError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, LOGGER

DATA_SCHEMA = probatio.Schema({probatio.Required(probatio.Secret(CONF_TOKEN)): str})


class NYTGamesConfigFlow(ConfigFlow, domain=DOMAIN):
    """NYT Games config flow."""

    async def _async_validate_token(
        self, token: str, errors: dict[str, str]
    ) -> int | None:
        """Validate the token and return the user id."""
        client = NYTGamesClient(token, session=async_create_clientsession(self.hass))
        try:
            return await client.get_user_id()
        except NYTGamesAuthenticationError:
            errors["base"] = "invalid_auth"
        except NYTGamesError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error")
            errors["base"] = "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            token = user_input[CONF_TOKEN].strip()
            user_id = await self._async_validate_token(token, errors)
            if user_id is not None:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="NYT Games", data={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication with a new token."""
        errors: dict[str, str] = {}
        if user_input:
            token = user_input[CONF_TOKEN].strip()
            user_id = await self._async_validate_token(token, errors)
            if user_id is not None:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration with a new token."""
        errors: dict[str, str] = {}
        if user_input:
            token = user_input[CONF_TOKEN].strip()
            user_id = await self._async_validate_token(token, errors)
            if user_id is not None:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reconfigure", data_schema=DATA_SCHEMA, errors=errors
        )
