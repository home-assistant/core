"""Config flow for the SMTP integration."""

from collections.abc import Mapping
from contextlib import suppress
import logging
from smtplib import SMTP, SMTP_SSL, SMTPAuthenticationError, SMTPException
import socket
from ssl import SSLCertVerificationError
from typing import Any, override

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import (
    SOURCE_USER,
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
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.selector import (
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

from . import SmtpConfigEntry
from .const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
    SECTION_OPTIONS,
    SUBENTRY_TYPE_RECIPIENT,
)

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=1800,
                    step=1,
                    unit_of_measurement=UnitOfTime.SECONDS,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        )
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENDER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
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
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
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
    }
)


class MailConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMTP."""

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: SmtpConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_RECIPIENT: RecipientSubentryFlowHandler}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: SmtpConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @override
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
            entry_data = user_input.copy()
            options = entry_data.pop(SECTION_OPTIONS)
            errors = await self.hass.async_add_executor_job(
                validate_input, entry_data, options
            )
            if not errors:
                return self.async_create_entry(
                    title=entry_data.get(CONF_SENDER_NAME, entry_data[CONF_SENDER]),
                    data=entry_data,
                    options=options,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA.extend(
                    {
                        vol.Required(SECTION_OPTIONS): data_entry_flow.section(
                            OPTIONS_SCHEMA,
                            {"collapsed": True},
                        ),
                    }
                ),
                suggested_values=user_input,
            ),
            errors=errors,
        )

    @override
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_SERVER: user_input[CONF_SERVER],
                    CONF_SENDER: user_input[CONF_SENDER],
                    CONF_USERNAME: user_input.get(CONF_USERNAME),
                }
            )
            errors = await self.hass.async_add_executor_job(
                validate_input, user_input, dict(entry.options)
            )
            if not errors:
                return self.async_update_and_abort(
                    entry,
                    data=user_input,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values=user_input or entry.data,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self.hass.async_add_executor_job(
                validate_input, {**entry.data, **user_input}, dict(entry.options)
            )
            if not errors:
                return self.async_update_and_abort(
                    entry,
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                suggested_values=user_input
                or {CONF_USERNAME: entry.data.get(CONF_USERNAME)},
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        options = {CONF_TIMEOUT: import_info.pop(CONF_TIMEOUT, DEFAULT_TIMEOUT)}
        self._async_abort_entries_match(import_info)

        errors = await self.hass.async_add_executor_job(
            validate_input, import_info, options
        )
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


def validate_input(
    user_input: dict[str, Any], options: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    errors: dict[str, str] = {}
    ssl_context = create_client_context() if user_input[CONF_VERIFY_SSL] else None
    mail: SMTP_SSL | SMTP | None = None
    try:
        if user_input[CONF_ENCRYPTION] == "tls":
            mail = SMTP_SSL(
                user_input[CONF_SERVER],
                user_input[CONF_PORT],
                timeout=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                context=ssl_context,
            )
        else:
            mail = SMTP(
                user_input[CONF_SERVER],
                user_input[CONF_PORT],
                timeout=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )
        mail.ehlo_or_helo_if_needed()
        if user_input[CONF_ENCRYPTION] == "starttls":
            mail.starttls(context=ssl_context)
            mail.ehlo()
        if user_input.get(CONF_USERNAME) and user_input.get(CONF_PASSWORD):
            mail.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

    except TimeoutError:
        errors["base"] = "timeout_connect"
    except SMTPAuthenticationError:
        errors["base"] = "invalid_auth"
    except SSLCertVerificationError:
        errors["base"] = "invalid_cert"
    except socket.gaierror, ConnectionRefusedError, SMTPException:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    finally:
        if mail is not None:
            with suppress(SMTPException):
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
                            type=TextSelectorType.EMAIL,
                            autocomplete="email",
                        ),
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure flow to update a recipient."""

        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            old_unique_id = subentry.unique_id
            result = self.async_update_and_abort(
                entry,
                subentry=subentry,
                title=(
                    user_input[CONF_RECIPIENT]
                    if subentry.title == old_unique_id
                    else subentry.title
                ),
                data_updates={},
                unique_id=user_input[CONF_RECIPIENT],
            )
            if result.get("reason") == "reconfigure_successful" and (
                entity := er.async_get(self.hass).async_get_entity_id(
                    NOTIFY_DOMAIN, DOMAIN, f"{entry.entry_id}_{old_unique_id}"
                )
            ):
                er.async_get(self.hass).async_update_entity(
                    entity,
                    new_unique_id=f"{entry.entry_id}_{user_input[CONF_RECIPIENT]}",
                )
            return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_RECIPIENT): TextSelector(
                            TextSelectorConfig(
                                type=TextSelectorType.EMAIL,
                                autocomplete="email",
                            ),
                        )
                    }
                ),
                suggested_values={CONF_RECIPIENT: subentry.unique_id},
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
