"""Config flow for SMTP integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
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
from .helpers import try_connect


def _build_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Build schema with suggested values from user input."""
    if user_input is None:
        user_input = {}

    return vol.Schema(
        {
            # Server settings (top section)
            vol.Required(
                CONF_SERVER,
                default=user_input.get(CONF_SERVER, DEFAULT_HOST),
            ): TextSelector(),
            vol.Required(
                CONF_PORT,
                default=user_input.get(CONF_PORT, DEFAULT_PORT),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_ENCRYPTION,
                default=user_input.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=ENCRYPTION_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_ENCRYPTION,
                )
            ),
            # Authentication
            vol.Optional(
                CONF_USERNAME,
                default=user_input.get(CONF_USERNAME, ""),
            ): TextSelector(),
            vol.Optional(
                CONF_PASSWORD,
                default=user_input.get(CONF_PASSWORD, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            # Email addresses
            vol.Required(
                CONF_SENDER,
                default=user_input.get(CONF_SENDER, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
            vol.Optional(
                CONF_SENDER_NAME,
                default=user_input.get(CONF_SENDER_NAME, ""),
            ): TextSelector(),
            vol.Required(
                CONF_RECIPIENT,
                default=user_input.get(CONF_RECIPIENT, ""),
            ): TextSelector(),
            # Advanced settings
            vol.Required(
                CONF_TIMEOUT,
                default=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=60, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
                )
            ),
            vol.Required(
                CONF_VERIFY_SSL,
                default=user_input.get(CONF_VERIFY_SSL, True),
            ): BooleanSelector(),
            vol.Required(
                CONF_DEBUG,
                default=user_input.get(CONF_DEBUG, DEFAULT_DEBUG),
            ): BooleanSelector(),
        }
    )


def _build_title(sender: str, sender_name: str | None = None) -> str:
    """Build config entry title from sender name and email."""
    if sender_name:
        return f"{sender_name} ({sender})"
    return sender


EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_recipients(raw: str) -> list[str] | None:
    """Parse and validate comma-separated email addresses.

    Returns list of addresses if valid, None if any are invalid.
    """
    recipients = [r.strip() for r in raw.split(",") if r.strip()]
    if not recipients:
        return None
    for addr in recipients:
        if not EMAIL_PATTERN.match(addr):
            return None
    return recipients


class SMTPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMTP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured with same sender
            self._async_abort_entries_match({CONF_SENDER: user_input[CONF_SENDER]})

            # Convert port to int (NumberSelector returns float)
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])

            # Validate recipients
            recipients = _validate_recipients(user_input[CONF_RECIPIENT])
            if recipients is None:
                errors[CONF_RECIPIENT] = "invalid_email"
            else:
                # Validate connection
                error = await self.hass.async_add_executor_job(
                    try_connect,
                    user_input[CONF_SERVER],
                    user_input[CONF_PORT],
                    user_input[CONF_TIMEOUT],
                    user_input[CONF_ENCRYPTION],
                    user_input.get(CONF_USERNAME) or None,
                    user_input.get(CONF_PASSWORD) or None,
                    user_input[CONF_VERIFY_SSL],
                )

                if error:
                    errors["base"] = error
                else:
                    data = {**user_input, CONF_RECIPIENT: recipients}

                    return self.async_create_entry(
                        title=_build_title(
                            user_input[CONF_SENDER],
                            user_input.get(CONF_SENDER_NAME),
                        ),
                        data=data,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        name = import_data.pop(CONF_NAME)

        # Use name as unique ID to prevent duplicate imports
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=_build_title(import_data[CONF_SENDER], name),
            data=import_data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Convert port to int (NumberSelector returns float)
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])

            # Keep existing password if empty
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = entry.data.get(CONF_PASSWORD, "")

            # Validate recipients
            recipients = _validate_recipients(user_input[CONF_RECIPIENT])
            if recipients is None:
                errors[CONF_RECIPIENT] = "invalid_email"
            else:
                # Validate connection
                error = await self.hass.async_add_executor_job(
                    try_connect,
                    user_input[CONF_SERVER],
                    user_input[CONF_PORT],
                    user_input[CONF_TIMEOUT],
                    user_input[CONF_ENCRYPTION],
                    user_input.get(CONF_USERNAME) or None,
                    user_input.get(CONF_PASSWORD) or None,
                    user_input[CONF_VERIFY_SSL],
                )

                if error:
                    errors["base"] = error
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={**user_input, CONF_RECIPIENT: recipients},
                        title=_build_title(
                            user_input[CONF_SENDER],
                            user_input.get(CONF_SENDER_NAME),
                        ),
                    )

        # Pre-fill with current values
        current = entry.data
        current_input = {
            CONF_SERVER: current.get(CONF_SERVER, DEFAULT_HOST),
            CONF_PORT: current.get(CONF_PORT, DEFAULT_PORT),
            CONF_ENCRYPTION: current.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION),
            CONF_USERNAME: current.get(CONF_USERNAME, ""),
            CONF_PASSWORD: "",
            CONF_SENDER: current.get(CONF_SENDER, ""),
            CONF_SENDER_NAME: current.get(CONF_SENDER_NAME, ""),
            CONF_RECIPIENT: ", ".join(current.get(CONF_RECIPIENT, [])),
            CONF_TIMEOUT: current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_VERIFY_SSL: current.get(CONF_VERIFY_SSL, True),
            CONF_DEBUG: current.get(CONF_DEBUG, DEFAULT_DEBUG),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(current_input),
            errors=errors,
        )
