"""Config Flow for the Vistapool integration."""

from collections.abc import Mapping
import logging
from typing import Any

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): cv.string})


class VistapoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Vistapool config flow (one entry per Hayward account)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(session, username, password)
            try:
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except AquariteError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(auth.user_id)
                self._abort_if_unique_id_configured()

                api = AquariteClient(auth)
                try:
                    pools = await api.get_pools()
                except AquariteError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error fetching pools")
                    errors["base"] = "unknown"
                else:
                    if not pools:
                        errors["base"] = "no_pools"
                    else:
                        return self.async_create_entry(
                            title=username,
                            data={
                                CONF_USERNAME: username,
                                CONF_PASSWORD: password,
                            },
                        )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauth flow when stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new password and validate against the same account."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        username = entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(session, username, password)
            try:
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except AquariteError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(auth.user_id)
                self._abort_if_unique_id_mismatch(reason="account_mismatch")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": username},
            errors=errors,
        )
