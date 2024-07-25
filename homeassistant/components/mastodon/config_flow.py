"""Config flow for Mastodon."""

from __future__ import annotations

from typing import Any

from mastodon.Mastodon import MastodonError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
)
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_BASE_URL, DEFAULT_NAME, DEFAULT_URL, DOMAIN, LOGGER
from .utils import create_mastodon_instance

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_NAME,
            default=DEFAULT_NAME,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(
            CONF_BASE_URL,
            default=DEFAULT_URL,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(
            CONF_CLIENT_ID,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Required(
            CONF_CLIENT_SECRET,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Required(
            CONF_ACCESS_TOKEN,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)


class MastodonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    config_entry: ConfigEntry

    async def check_connection(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        access_token: str,
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Check connection to the Mastodon instance."""
        try:
            client = await self.hass.async_add_executor_job(
                create_mastodon_instance,
                base_url,
                client_id,
                client_secret,
                access_token,
            )
            account = await self.hass.async_add_executor_job(
                client.account_verify_credentials
            )

        except MastodonError:
            return {"base": "credential_error"}, None
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error")
            return {"base": "unknown"}, None
        return {}, account

    def show_user_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
        step_id: str = "user",
    ) -> ConfigFlowResult:
        """Show the user form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self.show_user_form()

        self._async_abort_entries_match({CONF_CLIENT_ID: user_input[CONF_CLIENT_ID]})

        errors, account = await self.check_connection(
            user_input[CONF_BASE_URL],
            user_input[CONF_CLIENT_ID],
            user_input[CONF_CLIENT_SECRET],
            user_input[CONF_ACCESS_TOKEN],
        )

        if errors:
            return self.show_user_form(user_input, errors)

        await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        LOGGER.debug("Importing Mastodon from configuration.yaml")

        name = import_config[CONF_NAME]
        base_url = import_config[CONF_BASE_URL]
        client_id = import_config[CONF_CLIENT_ID]
        client_secret = import_config[CONF_CLIENT_SECRET]
        access_token = import_config[CONF_ACCESS_TOKEN]

        self._async_abort_entries_match(
            {
                CONF_NAME: name,
                CONF_BASE_URL: base_url,
                CONF_CLIENT_ID: client_id,
                CONF_CLIENT_SECRET: client_secret,
                CONF_ACCESS_TOKEN: access_token,
            }
        )

        errors, account = await self.check_connection(
            base_url, client_id, client_secret, access_token
        )

        if errors:
            return self.async_abort(reason="import_failed")

        await self.async_set_unique_id(client_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={
                CONF_NAME: name,
                CONF_BASE_URL: base_url,
                CONF_CLIENT_ID: client_id,
                CONF_CLIENT_SECRET: client_secret,
                CONF_ACCESS_TOKEN: access_token,
            },
        )
