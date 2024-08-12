"""Config flow for Mastodon."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mastodon.Mastodon import MastodonNetworkError, MastodonUnauthorizedError
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
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BASE_URL, DEFAULT_URL, DOMAIN, LOGGER
from .utils import construct_mastodon_username, create_mastodon_client

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
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

REAUTH_SCHEMA = vol.Schema(
    {
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
    config_entry: ConfigEntry | None = None
    base_url: str

    def check_connection(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        access_token: str,
    ) -> tuple[
        dict[str, str] | None,
        dict[str, str] | None,
        dict[str, str],
    ]:
        """Check connection to the Mastodon instance."""
        try:
            client = create_mastodon_client(
                base_url,
                client_id,
                client_secret,
                access_token,
            )
            instance = client.instance()
            account = client.account_verify_credentials()

        except MastodonNetworkError:
            return None, None, {"base": "network_error"}
        except MastodonUnauthorizedError:
            return None, None, {"base": "unauthorized_error"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error")
            return None, None, {"base": "unknown"}
        return instance, account, {}

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
        errors: dict[str, str] | None = None
        if user_input:
            self._async_abort_entries_match(
                {CONF_CLIENT_ID: user_input[CONF_CLIENT_ID]}
            )

            instance, account, errors = await self.hass.async_add_executor_job(
                self.check_connection,
                user_input[CONF_BASE_URL],
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
                user_input[CONF_ACCESS_TOKEN],
            )

            if not errors:
                name = construct_mastodon_username(instance, account)
                await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.show_user_form(user_input, errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.base_url = entry_data[CONF_BASE_URL]
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input:
            _, _, errors = await self.hass.async_add_executor_job(
                self.check_connection,
                self.base_url,
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
                user_input[CONF_ACCESS_TOKEN],
            )

            if not errors:
                assert self.config_entry
                # Access token only used to auth but as client_id originally captured and
                # used as unique_id we capture again/validate to avoid switching accounts.
                if self.config_entry.unique_id == user_input[CONF_CLIENT_ID]:
                    return self.async_update_reload_and_abort(
                        self.config_entry,
                        data={
                            **self.config_entry.data,
                            CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                            CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                            CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                        },
                    )
                return self.async_abort(reason="wrong_client_key")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        errors: dict[str, str] | None = None

        LOGGER.debug("Importing Mastodon from configuration.yaml")

        base_url = str(import_config.get(CONF_BASE_URL, DEFAULT_URL))
        client_id = str(import_config.get(CONF_CLIENT_ID))
        client_secret = str(import_config.get(CONF_CLIENT_SECRET))
        access_token = str(import_config.get(CONF_ACCESS_TOKEN))
        name = import_config.get(CONF_NAME, None)

        instance, account, errors = await self.hass.async_add_executor_job(
            self.check_connection,
            base_url,
            client_id,
            client_secret,
            access_token,
        )

        if not errors:
            await self.async_set_unique_id(client_id)
            self._abort_if_unique_id_configured()

            if not name:
                name = construct_mastodon_username(instance, account)

            return self.async_create_entry(
                title=name,
                data={
                    CONF_BASE_URL: base_url,
                    CONF_CLIENT_ID: client_id,
                    CONF_CLIENT_SECRET: client_secret,
                    CONF_ACCESS_TOKEN: access_token,
                },
            )

        reason = next(iter(errors.items()))[1]
        return self.async_abort(reason=reason)
