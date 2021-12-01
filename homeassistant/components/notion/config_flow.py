"""Config flow to configure the Notion integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aionotion import async_get_client
from aionotion.errors import InvalidCredentialsError, NotionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
RE_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class NotionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Notion config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._password: str | None = None
        self._username: str | None = None

    async def _async_verify(self, step_id: str, schema: vol.Schema) -> FlowResult:
        """Attempt to authenticate the provided credentials."""
        if TYPE_CHECKING:
            assert self._username
            assert self._password

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await async_get_client(self._username, self._password, session=session)
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except NotionError as err:
            LOGGER.error("Unknown Notion error: %s", err)
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id=step_id,
                data_schema=schema,
                errors=errors,
                description_placeholders={CONF_USERNAME: self._username},
            )

        data = {CONF_USERNAME: self._username, CONF_PASSWORD: self._password}

        if existing_entry := await self.async_set_unique_id(self._username):
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=self._username, data=data)

    async def async_step_reauth(self, config: ConfigType) -> FlowResult:
        """Handle configuration by re-auth."""
        self._username = config[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=RE_AUTH_SCHEMA,
                description_placeholders={CONF_USERNAME: self._username},
            )

        self._password = user_input[CONF_PASSWORD]

        return await self._async_verify("reauth_confirm", RE_AUTH_SCHEMA)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=AUTH_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_verify("user", AUTH_SCHEMA)
