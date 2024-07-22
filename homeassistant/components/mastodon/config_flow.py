"""Config flow for Mastodon."""

from __future__ import annotations

from typing import Any

from mastodon.Mastodon import MastodonError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import CONF_BASE_URL, DEFAULT_NAME, DEFAULT_URL, DOMAIN, LOGGER
from .utils import create_mastodon_instance


class MastodonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    config_entry: ConfigEntry
    base_url: str | None = None

    async def check_connection(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Check connection to the Mastodon instance."""
        assert self.base_url is not None
        try:
            client = await self.hass.async_add_executor_job(
                create_mastodon_instance,
                self.base_url,
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
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, DEFAULT_NAME),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                    vol.Required(
                        CONF_BASE_URL,
                        default=user_input.get(CONF_BASE_URL, DEFAULT_URL),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                    vol.Required(
                        CONF_CLIENT_ID, default=user_input.get(CONF_CLIENT_ID, "")
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                    vol.Required(
                        CONF_CLIENT_SECRET,
                        default=user_input.get(CONF_CLIENT_SECRET, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                    vol.Required(
                        CONF_ACCESS_TOKEN, default=user_input.get(CONF_ACCESS_TOKEN, "")
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    def abort_on_import_error(self, client_id: str, error: str) -> ConfigFlowResult:
        """Abort import flow on error."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"import_yaml_error_{DOMAIN}_{slugify(client_id)}",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="import_yaml_error",
            translation_placeholders={"client_id": client_id},
        )
        return self.async_abort(reason=error)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self.show_user_form()

        self._async_abort_entries_match({CONF_CLIENT_ID: user_input[CONF_CLIENT_ID]})

        self.base_url = user_input[CONF_BASE_URL]

        errors, account = await self.check_connection(
            user_input[CONF_CLIENT_ID],
            user_input[CONF_CLIENT_SECRET],
            user_input[CONF_ACCESS_TOKEN],
        )

        if errors:
            if self.context["source"] == SOURCE_IMPORT:
                return self.abort_on_import_error(
                    user_input[CONF_CLIENT_ID], "credential_error"
                )
            return self.show_user_form(user_input, errors)

        await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle an import flow."""
        return await self.async_step_user(
            {
                CONF_NAME: user_input[CONF_NAME],
                CONF_BASE_URL: user_input[CONF_BASE_URL],
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
            }
        )
