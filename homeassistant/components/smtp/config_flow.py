"""Config flow for SMTP integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
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
                        title=user_input[CONF_SENDER],
                        data=data,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SMTPOptionsFlow:
        """Get the options flow for this handler."""
        return SMTPOptionsFlow()


UNCHANGED_PASSWORD = "__UNCHANGED__"


def _build_options_schema(user_input: dict[str, Any], has_password: bool) -> vol.Schema:
    """Build schema for options flow with password placeholder."""
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
                description={
                    "suggested_value": UNCHANGED_PASSWORD if has_password else ""
                },
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


class SMTPOptionsFlow(OptionsFlow):
    """Handle SMTP options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = self.config_entry.data
        has_password = bool(current.get(CONF_PASSWORD))

        if user_input is not None:
            # Convert port to int (NumberSelector returns float)
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])

            # Keep existing password if unchanged
            password = user_input.get(CONF_PASSWORD)
            if password == UNCHANGED_PASSWORD or not password:
                user_input[CONF_PASSWORD] = current.get(CONF_PASSWORD, "")

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
                    new_data = {**user_input, CONF_RECIPIENT: recipients}

                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                        title=user_input[CONF_SENDER],
                    )
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                    return self.async_create_entry(title="", data={})

        # Build current values for the form
        current_input = {
            CONF_SERVER: current.get(CONF_SERVER, DEFAULT_HOST),
            CONF_PORT: current.get(CONF_PORT, DEFAULT_PORT),
            CONF_ENCRYPTION: current.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION),
            CONF_USERNAME: current.get(CONF_USERNAME, ""),
            CONF_SENDER: current.get(CONF_SENDER, ""),
            CONF_SENDER_NAME: current.get(CONF_SENDER_NAME, ""),
            CONF_RECIPIENT: ", ".join(current.get(CONF_RECIPIENT, [])),
            CONF_TIMEOUT: current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_VERIFY_SSL: current.get(CONF_VERIFY_SSL, True),
            CONF_DEBUG: current.get(CONF_DEBUG, DEFAULT_DEBUG),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(current_input, has_password),
            errors=errors,
        )
