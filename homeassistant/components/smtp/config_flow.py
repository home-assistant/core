"""Config flow for SMTP integration."""

from __future__ import annotations

import contextlib
import smtplib
import socket
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


def _try_connect(
    server: str,
    port: int,
    timeout: int,
    encryption: str,
    username: str | None,
    password: str | None,
    verify_ssl: bool,
) -> str | None:
    """Try to connect to the SMTP server and return error key if failed."""
    from homeassistant.util.ssl import client_context

    # Ignore verify_ssl when no encryption is used
    if encryption == "none":
        verify_ssl = False

    ssl_context = client_context() if verify_ssl else None
    mail: smtplib.SMTP_SSL | smtplib.SMTP | None = None

    try:
        if encryption == "tls":
            mail = smtplib.SMTP_SSL(
                server,
                port,
                timeout=timeout,
                context=ssl_context,
            )
        else:
            mail = smtplib.SMTP(server, port, timeout=timeout)

        mail.ehlo_or_helo_if_needed()

        if encryption == "starttls":
            mail.starttls(context=ssl_context)
            mail.ehlo()

        if username and password:
            mail.login(username, password)

        return None

    except smtplib.SMTPAuthenticationError:
        return "invalid_auth"
    except smtplib.SMTPException:
        return "cannot_connect"
    except (socket.gaierror, ConnectionRefusedError, TimeoutError, OSError):
        return "cannot_connect"
    finally:
        if mail:
            with contextlib.suppress(smtplib.SMTPException):
                mail.quit()


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

            # Validate connection
            error = await self.hass.async_add_executor_job(
                _try_connect,
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
                # Convert recipient to list for storage
                recipients = [
                    r.strip()
                    for r in user_input[CONF_RECIPIENT].split(",")
                    if r.strip()
                ]
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
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return SMTPOptionsFlow(config_entry)


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

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = self._config_entry.data
        has_password = bool(current.get(CONF_PASSWORD))

        if user_input is not None:
            # Convert port to int (NumberSelector returns float)
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])

            # Keep existing password if unchanged
            password = user_input.get(CONF_PASSWORD)
            if password == UNCHANGED_PASSWORD or not password:
                user_input[CONF_PASSWORD] = current.get(CONF_PASSWORD, "")

            # Validate connection
            error = await self.hass.async_add_executor_job(
                _try_connect,
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
                # Convert recipient to list for storage
                recipients = [
                    r.strip()
                    for r in user_input[CONF_RECIPIENT].split(",")
                    if r.strip()
                ]
                new_data = {**user_input, CONF_RECIPIENT: recipients}

                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=new_data,
                    title=user_input[CONF_SENDER],
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
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
