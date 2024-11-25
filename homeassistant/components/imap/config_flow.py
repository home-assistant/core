"""Config flow for imap integration."""

from __future__ import annotations

from collections.abc import Mapping
import ssl
from typing import Any

from aioimaplib import AioImapException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TemplateSelectorConfig,
)
from homeassistant.util.ssl import SSLCipherList

from .const import (
    CONF_CHARSET,
    CONF_CUSTOM_EVENT_DATA_TEMPLATE,
    CONF_ENABLE_PUSH,
    CONF_EVENT_MESSAGE_DATA,
    CONF_FOLDER,
    CONF_MAX_MESSAGE_SIZE,
    CONF_SEARCH,
    CONF_SERVER,
    CONF_SSL_CIPHER_LIST,
    DEFAULT_MAX_MESSAGE_SIZE,
    DEFAULT_PORT,
    DOMAIN,
    MAX_MESSAGE_SIZE_LIMIT,
    MESSAGE_DATA_OPTIONS,
)
from .coordinator import connect_to_server
from .errors import InvalidAuth, InvalidFolder

BOOLEAN_SELECTOR = BooleanSelector()
CIPHER_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(SSLCipherList),
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_SSL_CIPHER_LIST,
    )
)
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())
EVENT_MESSAGE_DATA_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=MESSAGE_DATA_OPTIONS,
        translation_key=CONF_EVENT_MESSAGE_DATA,
        multiple=True,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERVER): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CHARSET, default="utf-8"): str,
        vol.Optional(CONF_FOLDER, default="INBOX"): str,
        vol.Optional(CONF_SEARCH, default="UnSeen UnDeleted"): str,
        # The default for new entries is to not include text and headers
        vol.Optional(CONF_EVENT_MESSAGE_DATA, default=[]): EVENT_MESSAGE_DATA_SELECTOR,
    }
)
CONFIG_SCHEMA_ADVANCED = {
    vol.Optional(
        CONF_SSL_CIPHER_LIST, default=SSLCipherList.PYTHON_DEFAULT
    ): CIPHER_SELECTOR,
    vol.Optional(CONF_VERIFY_SSL, default=True): BOOLEAN_SELECTOR,
}

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FOLDER, default="INBOX"): str,
        vol.Optional(CONF_SEARCH, default="UnSeen UnDeleted"): str,
        # The default for older entries is to include text and headers
        vol.Optional(
            CONF_EVENT_MESSAGE_DATA, default=MESSAGE_DATA_OPTIONS
        ): EVENT_MESSAGE_DATA_SELECTOR,
    }
)

OPTIONS_SCHEMA_ADVANCED = {
    vol.Optional(CONF_CUSTOM_EVENT_DATA_TEMPLATE): TEMPLATE_SELECTOR,
    vol.Optional(CONF_MAX_MESSAGE_SIZE, default=DEFAULT_MAX_MESSAGE_SIZE): vol.All(
        cv.positive_int,
        vol.Range(min=DEFAULT_MAX_MESSAGE_SIZE, max=MAX_MESSAGE_SIZE_LIMIT),
    ),
    vol.Optional(CONF_ENABLE_PUSH, default=True): BOOLEAN_SELECTOR,
}


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate user input."""
    errors = {}

    try:
        imap_client = await connect_to_server(user_input)
        result, lines = await imap_client.search(
            user_input[CONF_SEARCH],
            charset=user_input[CONF_CHARSET],
        )

    except InvalidAuth:
        errors[CONF_USERNAME] = errors[CONF_PASSWORD] = "invalid_auth"
    except InvalidFolder:
        errors[CONF_FOLDER] = "invalid_folder"
    except ssl.SSLError:
        # The aioimaplib library 1.0.1 does not raise an ssl.SSLError correctly, but is logged
        # See https://github.com/bamthomas/aioimaplib/issues/91
        # This handler is added to be able to supply a better error message
        errors["base"] = "ssl_error"
    except (TimeoutError, AioImapException, ConnectionRefusedError):
        errors["base"] = "cannot_connect"
    else:
        if result != "OK":
            if "The specified charset is not supported" in lines[0].decode("utf-8"):
                errors[CONF_CHARSET] = "invalid_charset"
            else:
                errors[CONF_SEARCH] = "invalid_search"

    return errors


class IMAPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for imap."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        schema = CONFIG_SCHEMA
        if self.show_advanced_options:
            schema = schema.extend(CONFIG_SCHEMA_ADVANCED)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        self._async_abort_entries_match(
            {
                key: user_input[key]
                for key in (CONF_USERNAME, CONF_SERVER, CONF_FOLDER, CONF_SEARCH)
            }
        )

        if not (errors := await validate_input(self.hass, user_input)):
            title = user_input[CONF_USERNAME]

            return self.async_create_entry(title=title, data=user_input)

        schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}
            if not (errors := await validate_input(self.hass, user_input)):
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_NAME: reauth_entry.title,
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ImapOptionsFlow:
        """Get the options flow for this handler."""
        return ImapOptionsFlow()


class ImapOptionsFlow(OptionsFlow):
    """Option flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] | None = None
        entry_data: dict[str, Any] = dict(self.config_entry.data)
        if user_input is not None:
            try:
                self._async_abort_entries_match(
                    {
                        CONF_SERVER: self.config_entry.data[CONF_SERVER],
                        CONF_USERNAME: self.config_entry.data[CONF_USERNAME],
                        CONF_FOLDER: user_input[CONF_FOLDER],
                        CONF_SEARCH: user_input[CONF_SEARCH],
                    }
                    if user_input
                    else None
                )
            except AbortFlow as err:
                errors = {"base": err.reason}
            else:
                entry_data.update(user_input)
                errors = await validate_input(self.hass, entry_data)
                if not errors:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=entry_data
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self.config_entry.entry_id
                        )
                    )
                    return self.async_create_entry(data={})

        schema = OPTIONS_SCHEMA
        if self.show_advanced_options:
            schema = schema.extend(OPTIONS_SCHEMA_ADVANCED)
        schema = self.add_suggested_values_to_schema(schema, entry_data)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
