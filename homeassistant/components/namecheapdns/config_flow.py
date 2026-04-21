"""Config flow for the Namecheap DynamicDNS integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DOMAIN, CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .helpers import AuthFailed, update_namecheapdns
from .issue import deprecate_yaml_issue

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="@"): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class NamecheapDnsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Namecheap DynamicDNS."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_DOMAIN: user_input[CONF_DOMAIN]}
            )
            session = async_get_clientsession(self.hass)
            try:
                if not await update_namecheapdns(session, **user_input):
                    errors["base"] = "update_failed"
            except ClientError:
                _LOGGER.debug("Cannot connect", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}.{user_input[CONF_DOMAIN]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={"account_panel": "https://ap.www.namecheap.com/"},
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        self._async_abort_entries_match(
            {CONF_HOST: import_info[CONF_HOST], CONF_DOMAIN: import_info[CONF_DOMAIN]}
        )
        result = await self.async_step_user(import_info)
        if errors := result.get("errors"):
            deprecate_yaml_issue(self.hass, import_success=False)
            return self.async_abort(reason=errors["base"])

        deprecate_yaml_issue(self.hass, import_success=True)
        return result

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = (
            self._get_reauth_entry()
            if self.source == SOURCE_REAUTH
            else self._get_reconfigure_entry()
        )

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                if not await update_namecheapdns(
                    session,
                    entry.data[CONF_HOST],
                    entry.data[CONF_DOMAIN],
                    user_input[CONF_PASSWORD],
                ):
                    errors["base"] = "update_failed"
            except AuthFailed:
                errors["base"] = "invalid_auth"
            except ClientError:
                _LOGGER.debug("Cannot connect", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm" if self.source == SOURCE_REAUTH else "reconfigure",
            data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "account_panel": f"https://ap.www.namecheap.com/Domains/DomainControlPanel/{entry.data[CONF_DOMAIN]}/advancedns",
                CONF_NAME: entry.title,
                CONF_DOMAIN: entry.data[CONF_DOMAIN],
            },
        )
