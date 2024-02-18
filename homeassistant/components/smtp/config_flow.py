"""Config flow for SMTP integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
)
from .notify import SMTPClient

_LOGGER = logging.getLogger(__name__)


BASE_DATA_FIELDS = {
    vol.Optional(CONF_NAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_RECIPIENT): SelectSelector(
        SelectSelectorConfig(options=[], multiple=True, custom_value=True)
    ),
    vol.Required(CONF_SENDER): TextSelector(
        TextSelectorConfig(type=TextSelectorType.EMAIL)
    ),
    vol.Required(CONF_SERVER, default=DEFAULT_HOST): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
        NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX, step=1)
    ),
    vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): SelectSelector(
        SelectSelectorConfig(options=ENCRYPTION_OPTIONS, translation_key="encryption")
    ),
    vol.Optional(CONF_USERNAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Optional(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_SENDER_NAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
}

ADVANCED_DATA_FIELDS = {
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
        NumberSelectorConfig(min=1, max=60, mode=NumberSelectorMode.BOX)
    ),
    vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): BooleanSelector(
        BooleanSelectorConfig()
    ),
    vol.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(
        BooleanSelectorConfig()
    ),
}

CONFIG_SCHEMA = vol.Schema(BASE_DATA_FIELDS | ADVANCED_DATA_FIELDS)

UNIQUE_ENTRY_KEYS = [CONF_RECIPIENT, CONF_SENDER, CONF_SERVER, CONF_NAME]


def validate_smtp_settings(settings: dict[str, Any], errors: dict[str, str]) -> None:
    """Validate SMTP connection settings."""
    try:
        for recipient in cv.ensure_list(settings[CONF_RECIPIENT]):
            vol.Email()(recipient)
    except vol.Invalid:
        errors[CONF_RECIPIENT] = "invalid_email_address"
    try:
        vol.Email()(settings[CONF_SENDER])
    except vol.Invalid:
        errors[CONF_SENDER] = "invalid_email_address"
    if settings.get(CONF_USERNAME) and not settings.get(CONF_PASSWORD):
        errors[CONF_PASSWORD] = "username_and_password"
    if settings.get(CONF_PASSWORD) and not settings.get(CONF_USERNAME):
        errors[CONF_USERNAME] = "username_and_password"

    if errors:
        return
    settings[CONF_PORT] = cv.positive_int(settings[CONF_PORT])
    settings[CONF_TIMEOUT] = cv.positive_int(settings[CONF_TIMEOUT])

    service_class = SMTPClient(
        settings[CONF_SERVER],
        settings[CONF_PORT],
        settings.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        settings[CONF_ENCRYPTION],
        settings.get(CONF_USERNAME),
        settings.get(CONF_PASSWORD),
        settings.get(CONF_DEBUG, DEFAULT_DEBUG),
        settings.get(CONF_VERIFY_SSL, True),
    )
    service_class.connection_is_valid(errors=errors)


class SMTPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMTP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {key: user_input[key] for key in UNIQUE_ENTRY_KEYS if key in user_input}
            )
            data: dict[str, Any] = CONFIG_SCHEMA(user_input)
            await self.hass.async_add_executor_job(validate_smtp_settings, data, errors)
            if not errors:
                name = data.get(CONF_NAME, "SMTP")
                return self.async_create_entry(title=name, data=data)

        fields = BASE_DATA_FIELDS
        if self.show_advanced_options:
            fields |= ADVANCED_DATA_FIELDS

        schema = self.add_suggested_values_to_schema(vol.Schema(fields), user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import configuration from yaml."""
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2023.9.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "SMTP",
            },
        )
        self._async_abort_entries_match(
            {key: config[key] for key in UNIQUE_ENTRY_KEYS if key in config}
        )
        config.pop(CONF_PLATFORM)
        config[CONF_RECIPIENT] = cv.ensure_list(config[CONF_RECIPIENT])
        config = CONFIG_SCHEMA(config)
        return self.async_create_entry(
            title=config.get(CONF_NAME, "SMTP"),
            data=config,
        )
