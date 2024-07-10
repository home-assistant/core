"""Config flow for Mealie."""

from collections.abc import Mapping
from typing import Any

from aiomealie import MealieAuthenticationError, MealieClient, MealieConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class MealieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Mealie config flow."""

    host: str | None = None
    entry: ConfigEntry | None = None

    async def check_connection(
        self, api_token: str
    ) -> tuple[dict[str, str], str | None]:
        """Check connection to the Mealie API."""
        assert self.host is not None
        client = MealieClient(
            self.host,
            token=api_token,
            session=async_get_clientsession(self.hass),
        )
        try:
            info = await client.get_user_info()
        except MealieConnectionError:
            return {"base": "cannot_connect"}, None
        except MealieAuthenticationError:
            return {"base": "invalid_auth"}, None
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error")
            return {"base": "unknown"}, None
        return {}, info.user_id

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            self.host = user_input[CONF_HOST]
            errors, user_id = await self.check_connection(
                user_input[CONF_API_TOKEN],
            )
            if not errors:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Mealie",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.host = entry_data[CONF_HOST]
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input:
            errors, user_id = await self.check_connection(
                user_input[CONF_API_TOKEN],
            )
            if not errors:
                assert self.entry
                if self.entry.unique_id == user_id:
                    return self.async_update_reload_and_abort(
                        self.entry,
                        data={
                            **self.entry.data,
                            CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                        },
                    )
                return self.async_abort(reason="wrong_account")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )
