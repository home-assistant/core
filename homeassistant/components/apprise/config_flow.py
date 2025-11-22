"""Config flow for Apprise."""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_FILE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AppriseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apprise."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            if user_input.get(CONF_FILE_URL):
                if user_input.get(CONF_URL):
                    input_options = {
                        CONF_FILE_URL: user_input[CONF_FILE_URL],
                        CONF_URL: user_input[CONF_URL],
                    }
                else:
                    input_options = {
                        CONF_FILE_URL: user_input[CONF_FILE_URL],
                    }
            elif user_input.get(CONF_URL):
                input_options = {
                    CONF_URL: user_input[CONF_URL],
                }
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(CONF_FILE_URL): str,
                            vol.Optional(CONF_URL): str,
                        }
                    ),
                    errors=errors,
                )
            # Validate connection to Apprise
            success = await validate_apprise_connection(
                self.hass,
                user_input,
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Apprise",
                    data={},
                    options=input_options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FILE_URL): str,
                    vol.Optional(CONF_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        result = await self.async_step_user(import_config)

        await deprecate_yaml_issue(self.hass, True)
        return result

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return AppriseOptionsFlowHandler()


class AppriseOptionsFlowHandler(OptionsFlow):
    """Handle Apprise options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Apprise options."""
        errors: dict[str, str] = {}
        options = self.config_entry.options

        if user_input:
            new_options = {
                CONF_FILE_URL: user_input.get(CONF_FILE_URL, ""),
                CONF_URL: user_input.get(CONF_URL, ""),
            }

        success = await validate_apprise_connection(
            self.hass,
            user_input,
        )
        if success:
            return self.async_create_entry(title="", data=new_options)

        errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FILE_URL, default=options.get(CONF_FILE_URL, "")
                    ): str,
                    vol.Optional(CONF_URL, default=options.get(CONF_URL, "")): str,
                }
            ),
        )


async def validate_apprise_connection(
    hass: HomeAssistant, user_input: dict[str, Any] | None
) -> bool:
    """Attempt to send a test message to Apprise."""

    if not user_input:
        return False

    file_url = user_input.get(CONF_FILE_URL)
    plain_url = user_input.get(CONF_URL)

    if file_url:
        url = f"{file_url}/notify/apprise"
    elif plain_url:
        url = plain_url
    else:
        return False

    data = {"body": "Home Assistant connection test"}

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, data=data) as resp,
        ):
            return resp.status == 200
    except (TimeoutError, aiohttp.ClientError):
        return False


async def deprecate_yaml_issue(
    hass: HomeAssistant,
    import_success: bool,
) -> None:
    """Create an issue to deprecate YAML config."""
    if import_success:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2026.2.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Apprise",
            },
        )
