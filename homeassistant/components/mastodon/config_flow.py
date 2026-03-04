"""Config flow for Mastodon."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mastodon.Mastodon import (
    Account,
    Instance,
    InstanceV2,
    MastodonNetworkError,
    MastodonNotFoundError,
    MastodonUnauthorizedError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import CONF_BASE_URL, DOMAIN, LOGGER
from .utils import construct_mastodon_username, create_mastodon_client

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_BASE_URL,
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
            CONF_ACCESS_TOKEN,
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
STEP_RECONFIGURE_SCHEMA = vol.Schema(
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

EXAMPLE_URL = "https://mastodon.social"


def base_url_from_url(url: str) -> str:
    """Return the base url from a url."""
    return str(URL(url).origin())


def remove_email_link(account_name: str) -> str:
    """Remove email link from account name."""

    # Replaces the @ with a HTML entity to prevent mailto links.
    return account_name.replace("@", "&#64;")


class MastodonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    base_url: str
    client_id: str
    client_secret: str
    access_token: str

    def check_connection(
        self,
    ) -> tuple[
        InstanceV2 | Instance | None,
        Account | None,
        dict[str, str],
    ]:
        """Check connection to the Mastodon instance."""
        try:
            client = create_mastodon_client(
                self.base_url,
                self.client_id,
                self.client_secret,
                self.access_token,
            )
            try:
                instance = client.instance_v2()
            except MastodonNotFoundError:
                instance = client.instance_v1()
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
            user_input[CONF_BASE_URL] = base_url_from_url(user_input[CONF_BASE_URL])

            self.base_url = user_input[CONF_BASE_URL]
            self.client_id = user_input[CONF_CLIENT_ID]
            self.client_secret = user_input[CONF_CLIENT_SECRET]
            self.access_token = user_input[CONF_ACCESS_TOKEN]

            instance, account, errors = await self.hass.async_add_executor_job(
                self.check_connection
            )

            if not errors:
                name = construct_mastodon_username(instance, account)
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.show_user_form(
            user_input,
            errors,
            description_placeholders={"example_url": EXAMPLE_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.base_url = entry_data[CONF_BASE_URL]
        self.client_id = entry_data[CONF_CLIENT_ID]
        self.client_secret = entry_data[CONF_CLIENT_SECRET]
        self.access_token = entry_data[CONF_ACCESS_TOKEN]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input:
            self.access_token = user_input[CONF_ACCESS_TOKEN]
            instance, account, errors = await self.hass.async_add_executor_job(
                self.check_connection
            )
            if not errors:
                name = construct_mastodon_username(instance, account)
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN]},
                )
        account_name = self._get_reauth_entry().title
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "account_name": remove_email_link(account_name),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}

        reconfigure_entry = self._get_reconfigure_entry()

        if user_input:
            self.base_url = reconfigure_entry.data[CONF_BASE_URL]
            self.client_id = user_input[CONF_CLIENT_ID]
            self.client_secret = user_input[CONF_CLIENT_SECRET]
            self.access_token = user_input[CONF_ACCESS_TOKEN]
            instance, account, errors = await self.hass.async_add_executor_job(
                self.check_connection
            )
            if not errors:
                name = construct_mastodon_username(instance, account)
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                    },
                )
        account_name = reconfigure_entry.title
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_RECONFIGURE_SCHEMA,
            errors=errors,
            description_placeholders={
                "account_name": remove_email_link(account_name),
            },
        )
