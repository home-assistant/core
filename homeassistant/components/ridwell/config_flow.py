"""Config flow for Ridwell integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from aioridwell import async_get_client
from aioridwell.errors import InvalidCredentialsError, RidwellError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN, LOGGER

STEP_REAUTH_CONFIRM_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class RidwellConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ridwell."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._password: str | None = None
        self._username: str | None = None

    async def _async_validate(
        self, error_step_id: str, error_schema: vol.Schema
    ) -> ConfigFlowResult:
        """Validate input credentials and proceed accordingly."""
        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        if TYPE_CHECKING:
            assert self._password
            assert self._username

        try:
            await async_get_client(self._username, self._password, session=session)
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except RidwellError as err:
            LOGGER.error("Unknown Ridwell error: %s", err)
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors=errors,
                description_placeholders={CONF_USERNAME: self._username},
            )

        if existing_entry := await self.async_set_unique_id(self._username):
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data={**existing_entry.data, CONF_PASSWORD: self._password},
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self._username,
            data={CONF_USERNAME: self._username, CONF_PASSWORD: self._password},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_CONFIRM_DATA_SCHEMA,
                description_placeholders={CONF_USERNAME: self._username},
            )

        self._password = user_input[CONF_PASSWORD]

        return await self._async_validate(
            "reauth_confirm", STEP_REAUTH_CONFIRM_DATA_SCHEMA
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_validate("user", STEP_USER_DATA_SCHEMA)
