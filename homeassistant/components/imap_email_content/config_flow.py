"""Config flow for imap_email_content integration."""
import re
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_FOLDER, CONF_SENDERS, CONF_SERVER, DEFAULT_PORT, DOMAIN
from .sensor import EmailReader

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_PORT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)),
    vol.Coerce(int),
)
_TEXT_SELECTOR = TextSelector()
_TEXTBOX_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): _TEXT_SELECTOR,
        vol.Required(CONF_SERVER): _TEXT_SELECTOR,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT_SELECTOR,
        vol.Required(CONF_USERNAME): _TEXT_SELECTOR,
        vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
        vol.Required(CONF_SENDERS): _TEXTBOX_SELECTOR,
        vol.Optional(CONF_VALUE_TEMPLATE): _TEXTBOX_SELECTOR,
        vol.Optional(CONF_FOLDER, default="INBOX"): _TEXT_SELECTOR,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SENDERS): [cv.string],
        vol.Optional(CONF_VALUE_TEMPLATE): cv.string,
        vol.Optional(CONF_FOLDER, default="INBOX"): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


def try_connection(config: dict[str, str]) -> bool:
    """Test the imap configuration."""
    try:
        reader = EmailReader(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_SERVER],
            config[CONF_PORT],
            config[CONF_FOLDER],
            config[CONF_VERIFY_SSL],
        )
        if reader.connect():
            return True
    # pylint: disable-next=broad-exception-caught
    except Exception:
        return False
    return False


def validate_senders(user_input: dict[str, Any]) -> str | None:
    """Validate the senders."""
    if CONF_SENDERS not in user_input:
        return None

    senders = user_input[CONF_SENDERS]
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"

    # pass the regular expression
    # and the string into the fullmatch() method
    def _valid_email(sender: str) -> str:
        if not re.fullmatch(regex, sender):
            raise ValueError("Not a valid sender address: {email}")
        return sender

    # if senders was imported from yaml we already have a list
    sender_list: list[str] = (
        senders if isinstance(senders, list) else senders.split(";")
    )
    try:
        new_list: list[str] = [_valid_email(sender.strip()) for sender in sender_list]
        senders_str = ""
        for sender in new_list:
            senders_str += f"; {sender}" if senders_str else f"{sender}"
    except ValueError:
        return None
    user_input[CONF_SENDERS] = new_list
    return senders_str


async def async_validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any] | MappingProxyType[str, Any],
    validated_input: dict[str, Any],
    errors: dict[str, str],
    options_flow: bool = False,
) -> vol.Schema:
    """Validate user input."""
    validated_input.update(user_input)
    # Translate senders to a list object
    if (senders_str := validate_senders(validated_input)) is None:
        errors["base"] = "invalid_senders"

    def def_value(value: str, default: Any = None) -> dict[str, Any]:
        return {"suggested_value": user_input.get(value, default)}

    filled_schema = {
        vol.Required(CONF_SERVER, description=def_value(CONF_SERVER)): _TEXT_SELECTOR,
        vol.Optional(
            CONF_PORT, description=def_value(CONF_PORT, DEFAULT_PORT)
        ): _PORT_SELECTOR,
        vol.Required(
            CONF_USERNAME, description=def_value(CONF_USERNAME)
        ): _TEXT_SELECTOR,
        vol.Required(
            CONF_PASSWORD, description=def_value(CONF_PASSWORD)
        ): _PASSWORD_SELECTOR,
        vol.Required(
            CONF_SENDERS,
            description={
                "suggested_value": senders_str or user_input.get(CONF_SENDERS)
            },
        ): _TEXTBOX_SELECTOR,
        vol.Optional(
            CONF_VALUE_TEMPLATE, description=def_value(CONF_VALUE_TEMPLATE)
        ): _TEXTBOX_SELECTOR,
        vol.Optional(CONF_FOLDER, description=def_value(CONF_FOLDER)): _TEXT_SELECTOR,
        vol.Optional(
            CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
        ): cv.boolean,
    }
    if not options_flow:
        filled_schema[
            vol.Optional(CONF_NAME, description=def_value(CONF_NAME))
        ] = _TEXT_SELECTOR

    if not await hass.async_add_executor_job(try_connection, user_input):
        errors["base"] = "cannot_connect"

    return vol.Schema(filled_schema)


class ImapEmailContentOptionsFlow(config_entries.OptionsFlow):
    """Option flow handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        validated_user_input: dict[str, Any] = {}
        errors: dict[str, str] = {}
        if user_input is not None:
            schema = await async_validate_input(
                self.hass, user_input, validated_user_input, errors
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=CONFIG_SCHEMA(validated_user_input),
                )
                return self.async_create_entry(title="", data={})
        else:
            schema = await async_validate_input(
                self.hass, self.config_entry.data, validated_user_input, errors
            )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        # Check for duplicate entries

        match_data = {
            CONF_NAME: user_input.get(CONF_NAME, user_input[CONF_USERNAME]),
            CONF_USERNAME: user_input.get(CONF_USERNAME),
            CONF_FOLDER: user_input.get(CONF_FOLDER),
            CONF_SERVER: user_input.get(CONF_SERVER),
        }
        if CONF_FOLDER in user_input:
            match_data[CONF_FOLDER] = user_input[CONF_FOLDER]
        if CONF_VALUE_TEMPLATE in user_input:
            match_data[CONF_VALUE_TEMPLATE] = user_input[CONF_VALUE_TEMPLATE]
        self._async_abort_entries_match(match_data)

        validated_user_input: dict[str, Any] = {}
        errors: dict[str, str] = {}
        schema = await async_validate_input(
            self.hass, user_input, validated_user_input, errors
        )
        if not errors:
            title = validated_user_input.pop(CONF_NAME)
            return self.async_create_entry(
                title=title, data=CONFIG_SCHEMA(validated_user_input)
            )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        # To be removed when YAML import is removed
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ImapEmailContentOptionsFlow:
        """Get the options flow for this handler."""
        return ImapEmailContentOptionsFlow(config_entry)
