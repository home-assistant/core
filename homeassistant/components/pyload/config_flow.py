"""Config flow for pyLoad integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, ISSUE_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, description={"suggested_value": DEFAULT_NAME}): str,
        vol.Required(
            CONF_HOST, description={"suggested_value": "homeassistant.local"}
        ): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input and try to connect to PyLoad."""

    session = async_create_clientsession(
        hass,
        user_input.get(CONF_VERIFY_SSL, True),
        cookie_jar=CookieJar(unsafe=True),
    )
    host = user_input[CONF_HOST]
    port = user_input[CONF_PORT]
    protocol = "https" if user_input[CONF_SSL] else "http"
    url = f"{protocol}://{host}:{port}/"
    pyload = PyLoadAPI(
        session,
        api_url=url,
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    await pyload.login()


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._async_abort_entries_match(
                    {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
                )
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""
        # in config yaml all variables are optional, but some have a default value
        config = {
            CONF_NAME: import_info.get(CONF_NAME, DEFAULT_NAME),
            CONF_HOST: import_info.get(CONF_HOST, DEFAULT_HOST),
            CONF_PASSWORD: import_info.get(CONF_PASSWORD, ""),
            CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_SSL: import_info.get(CONF_SSL, False),
            CONF_USERNAME: import_info.get(CONF_USERNAME, ""),
            CONF_VERIFY_SSL: False,
        }

        result = await self.async_step_user(config)
        # Raise an issue that this is deprecated and has been imported
        if (
            result.get("type") == FlowResultType.CREATE_ENTRY
            or result.get("reason") == "already_configured"
        ):
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                is_fixable=False,
                issue_domain=DOMAIN,
                breaks_in_ha_version="2025.2.0",
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "pyLoad",
                },
            )
        elif errors := result.get("errors"):
            error = errors["base"]

            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{error}",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{error}",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )

        return result
