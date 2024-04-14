"""Config flow for pyLoad integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DEFAULT_PORT, DOMAIN
from .util import api_url

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=pyload"}


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1
    config_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := await self.async_auth(user_input)):
                self._async_abort_entries_match(
                    {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
                )
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        assert self.config_entry
        username = self.config_entry.data[CONF_USERNAME]
        if user_input is not None:
            new_input = self.config_entry.data | user_input
            if not (errors := await self.async_auth(new_input)):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_input
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_input
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: username},
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""
        # Raise an issue that this is deprecated and has been imported
        config = {
            CONF_HOST: import_info[CONF_HOST],
            CONF_PASSWORD: import_info.get(CONF_PASSWORD),
            CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_SSL: import_info.get(CONF_SSL, False),
            CONF_USERNAME: import_info.get(CONF_USERNAME),
            CONF_VERIFY_SSL: True,
        }

        result = await self.async_step_user(config)

        if (
            result.get("type") == FlowResultType.CREATE_ENTRY
            or result.get("reason") == "already_configured"
        ):
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                is_fixable=False,
                breaks_in_ha_version="2024.11.0",
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "pyLoad",
                },
            )
        else:
            error = result.get("reason")
            if errors := result.get("errors"):
                error = errors["base"]

            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{error}",
                breaks_in_ha_version="2024.12.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{error}",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )

        return result

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reconfiguration."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reconfiguration."""
        errors = {}

        assert self.config_entry
        if user_input is not None:
            new_input = self.config_entry.data | user_input
            if not (errors := await self.async_auth(new_input)):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_input
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values=self.config_entry.data,
            ),
            errors=errors,
        )

    async def async_auth(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Auth Helper."""

        errors: dict[str, str] = {}
        session = async_create_clientsession(
            self.hass,
            user_input.get(CONF_VERIFY_SSL, True),
            cookie_jar=CookieJar(unsafe=True),
        )
        pyload = PyLoadAPI(
            session,
            api_url(user_input),
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )
        try:
            await pyload.login()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors
