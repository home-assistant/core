"""Config flow to configure the Notion integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aionotion import async_get_client
from aionotion.errors import InvalidCredentialsError, NotionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, LOGGER

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


async def async_validate_credentials(
    hass: HomeAssistant, username: str, password: str
) -> dict[str, Any]:
    """Validate a Notion username and password (returning any errors)."""
    session = aiohttp_client.async_get_clientsession(hass)
    errors = {}

    try:
        await async_get_client(
            username, password, session=session, use_legacy_auth=True
        )
    except InvalidCredentialsError:
        errors["base"] = "invalid_auth"
    except NotionError as err:
        LOGGER.error("Unknown Notion error while validation credentials: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error while validation credentials: %s", err)
        errors["base"] = "unknown"

    return errors


class NotionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Notion config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        assert self._reauth_entry

        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                description_placeholders={
                    CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
                },
            )

        if errors := await async_validate_credentials(
            self.hass, self._reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
        ):
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                errors=errors,
                description_placeholders={
                    CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
                },
            )

        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=self._reauth_entry.data | user_input
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=AUTH_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        if errors := await async_validate_credentials(
            self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        ):
            return self.async_show_form(
                step_id="user",
                data_schema=AUTH_SCHEMA,
                errors=errors,
            )

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
