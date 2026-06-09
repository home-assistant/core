"""Config flow for the SMTP integration."""

import logging
from smtplib import SMTP, SMTP_SSL, SMTPAuthenticationError
import socket
from ssl import SSLCertVerificationError
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    FlowType,
    OptionsFlow,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_DEBUG,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
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
from homeassistant.util.ssl import create_client_context

from .const import (
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
    SUBENTRY_TYPE_RECIPIENT,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENDER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="email",
            ),
        ),
        vol.Optional(CONF_SENDER_NAME): cv.string,
        vol.Required(CONF_SERVER, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): SelectSelector(
            SelectSelectorConfig(
                options=ENCRYPTION_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="encryption",
            )
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(
                min=1,
                unit_of_measurement=UnitOfTime.SECONDS,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): BooleanSelector(),
    }
)


class MailConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMTP."""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_RECIPIENT: RecipientSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_SERVER: user_input[CONF_SERVER],
                    CONF_SENDER: user_input[CONF_SENDER],
                    CONF_USERNAME: user_input.get(CONF_USERNAME),
                }
            )
            errors = await self.hass.async_add_executor_job(validate_input, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_SENDER_NAME, user_input[CONF_SENDER]),
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Start subentry flow after creating main entry."""
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_RECIPIENT),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        options = {
            CONF_DEBUG: import_info.pop(CONF_DEBUG, DEFAULT_DEBUG),
            CONF_TIMEOUT: import_info.pop(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        self._async_abort_entries_match(import_info)

        errors = await self.hass.async_add_executor_job(validate_input, import_info)
        if not errors:
            title = (
                import_info.get(CONF_NAME)
                or import_info.get(CONF_SENDER_NAME)
                or import_info[CONF_SENDER]
            )
            return self.async_create_entry(
                title=title,
                data=import_info,
                options=options,
                subentries=[
                    ConfigSubentryData(
                        subentry_type=SUBENTRY_TYPE_RECIPIENT,
                        title=recipient,
                        unique_id=recipient,
                        data={},
                    )
                    for recipient in import_info[CONF_RECIPIENT]
                ],
            )

        return self.async_abort(reason=errors["base"])


def validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    errors: dict[str, str] = {}
    ssl_context = create_client_context() if user_input[CONF_VERIFY_SSL] else None
    mail: SMTP_SSL | SMTP | None = None
    try:
        if user_input[CONF_ENCRYPTION] == "tls":
            mail = SMTP_SSL(
                user_input[CONF_SERVER],
                user_input[CONF_PORT],
                timeout=DEFAULT_TIMEOUT,
                context=ssl_context,
            )
        else:
            mail = SMTP(
                user_input[CONF_SERVER], user_input[CONF_PORT], timeout=DEFAULT_TIMEOUT
            )
        mail.ehlo_or_helo_if_needed()
        if user_input[CONF_ENCRYPTION] == "starttls":
            mail.starttls(context=ssl_context)
            mail.ehlo()
        if user_input.get(CONF_USERNAME) and user_input.get(CONF_PASSWORD):
            mail.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

    except SMTPAuthenticationError:
        errors["base"] = "invalid_auth"
    except SSLCertVerificationError:
        errors["base"] = "invalid_cert"
    except socket.gaierror, ConnectionRefusedError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    finally:
        if mail is not None:
            mail.quit()

    return errors


class RecipientSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding an email recipient."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new recipient."""

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, user_input[CONF_RECIPIENT]),
                data={},
                unique_id=user_input[CONF_RECIPIENT],
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Required(CONF_RECIPIENT): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                            autocomplete="email",
                        ),
                    ),
                }
            ),
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
