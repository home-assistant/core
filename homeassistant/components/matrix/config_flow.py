"""Config flow for the Matrix integration."""
from __future__ import annotations

import json
import os
from typing import Any, Final

from matrix_client.client import MatrixClient
from matrix_client.errors import MatrixHttpLibError, MatrixRequestError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from . import MatrixAuthentication
from .const import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_HOMESERVER,
    CONF_ROOMS,
    CONF_WORD,
    DOMAIN,
    SESSION_FILE,
)

OPTION_LIST_COMMAND: Final = "list_command"
OPTION_ADD_COMMAND: Final = "add_command"
OPTION_DELETE_COMMAND: Final = "delete_command"

ROOMS_SCHEMA: vol.Schema = vol.All(cv.ensure_list, [cv.string])

COMMAND_SCHEMA: vol.Schema = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_WORD): cv.string,
            vol.Optional(CONF_EXPRESSION): cv.is_regex,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ROOMS, default=[]): ROOMS_SCHEMA,
            vol.Optional(OPTION_DELETE_COMMAND, default=False): cv.boolean,
        },
    ),
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION),
)

CONFIG_FLOW_ADDITIONAL_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_HOMESERVER): cv.url,
        vol.Required(CONF_USERNAME): cv.matches_regex("@[^:]*:.*"),
    },
    extra=vol.ALLOW_EXTRA,
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to log in.

    :return: A dict containing the title and the access token corresponding to the settings provided by the input data.
    :raises vol.Invalid: if the format check fails
    :raises vol.MultipleInvalid: if multiple format checks fail
    :raises MatrixHttpLibError: if the connection fails
    :raises MatrixRequestError: if login fails
    """

    # Check the format
    CONFIG_FLOW_ADDITIONAL_SCHEMA(data)

    auth: MatrixAuthentication = MatrixAuthentication(
        config_file=os.path.join(hass.config.path(), SESSION_FILE),
        homeserver=data[CONF_HOMESERVER],
        verify_ssl=data[CONF_VERIFY_SSL],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    # Check if we can log in
    client: MatrixClient = await hass.async_add_executor_job(auth.login)

    # If no exception is thrown during logging in
    token: str | None = ""
    if hasattr(client, "token"):
        # A new token will be assigned on first login
        token = client.token
    else:
        # Use the token from the previous login if there is no token from the client
        token = auth.auth_token(data[CONF_USERNAME])

    return {
        "title": data[CONF_USERNAME],
        CONF_ACCESS_TOKEN: token,
    }


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Matrix."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is None:
            user_input = {}
        else:
            try:
                info: dict[str, str] = await validate_input(self.hass, user_input)

            except MatrixHttpLibError:
                # Network error
                errors[CONF_BASE] = "cannot_connect"

            except MatrixRequestError as ex:
                # Error code definitions: https://spec.matrix.org/latest/client-server-api/#standard-error-response
                try:
                    error_code: Final[str] = json.loads(ex.content).get("errcode")

                except ValueError:
                    # The error content is not a valid JSON string.
                    errors[CONF_BASE] = "unknown"

                else:
                    if error_code in ("M_FORBIDDEN", "M_UNAUTHORIZED"):
                        errors[CONF_PASSWORD] = "invalid_auth"
                    elif error_code in ("M_INVALID_USERNAME", "M_USER_DEACTIVATED"):
                        errors[CONF_USERNAME] = "invalid_auth"
                    elif error_code in ("M_UNKNOWN_TOKEN", "M_MISSING_TOKEN"):
                        errors[CONF_BASE] = "invalid_access_token"
                    else:
                        errors[CONF_BASE] = "unknown"

            else:
                # Use access token as unique id as it can't be duplicated
                await self.async_set_unique_id(info[CONF_ACCESS_TOKEN])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOMESERVER,
                        default=user_input.get(CONF_HOMESERVER)
                        or "https://matrix-client.matrix.org",
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL) or True
                    ): bool,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Matrix integration options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """
        Gather information from the current config entry.

        self._options can contain:
        - CONF_ROOMS: [str]
        - CONF_COMMANDS: [dict[str, str | list[str]]
        """
        self._options: dict[str, Any] = dict(config_entry.options)

        self._commands: dict[str, dict[str, Any]] = {}

        """
        config_entry.options.get(CONF_COMMANDS, []) can return:
        [
            {
                CONF_WORD: str,
                CONF_EXPRESSION: str,
                CONF_NAME: str,
                CONF_ROOMS: [str],
            },
            ...
        ]
        """
        for command in config_entry.options.get(CONF_COMMANDS, []):
            self._commands[command[CONF_NAME]] = command

        # Used in self.async_step_add_remove_command to store the command name that is currently being handled.
        self.__current_command_name: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manage the options.

        Some possible procedures:
        - Main step -> (User: Do nothing and submit) -> End
        - Main step -> (User: Change CONF_ROOMS) -> <ROOMS_SCHEMA check passes> -> [Update CONF_ROOMS] -> [Save new options] -> End
                                                 -> <ROOMS_SCHEMA check fails>  -> Main step with error information -> ...
        - Main step -> (User: Choose an option in the list) -> Command step -> (User: Add/modify a command) -> <COMMAND_SCHEMA check passes> -> [Update self._commands] -> Main step
                                                                                                               <COMMAND_SCHEMA check fails>  -> Command step with error information -> ...
        - Main step -> (User: Change CONF_ROOMS and choose an option in the list) -> <ROOMS_SCHEMA check passes> -> Command step -> ...
                                                                                     <ROOMS_SCHEMA check fails>  -> Main step with error information -> ...
        """

        if user_input is not None:
            # CONF_ROOMS: convert str to list because voluptuous_serialize does not support List type
            user_input[CONF_ROOMS] = (
                user_input[CONF_ROOMS].split(",") if user_input[CONF_ROOMS] else []
            )

            # Check the format of CONF_ROOMS if it's not empty
            if user_input[CONF_ROOMS]:
                ROOMS_SCHEMA(user_input[CONF_ROOMS])

            # Update CONF_ROOMS
            self._options[CONF_ROOMS] = user_input[CONF_ROOMS]

            if user_input[CONF_COMMANDS] == OPTION_LIST_COMMAND:
                # Update CONF_COMMANDS
                self._options[CONF_COMMANDS] = list(self._commands.values())
                # Call async_create_entry and exit
                return self.async_create_entry(title="", data=self._options)
            elif user_input[CONF_COMMANDS] == OPTION_ADD_COMMAND:
                # Add a new command
                return await self.async_step_add_command(user_input=None)
            elif user_input[CONF_COMMANDS] in self._commands:
                # Modify/Delete an existing command
                return await self.async_step_modify_command(
                    user_input=self._commands[user_input[CONF_COMMANDS]]
                )

        return self._show_main_form()

    async def async_step_add_command(
        self, user_input: dict[str, Any] | None, is_add: bool = False
    ) -> FlowResult:
        """Add commands step."""
        return self._show_add_remove_command_form(user_input=user_input, is_add=True)

    async def async_step_modify_command(
        self, user_input: dict[str, Any] | None, is_add: bool = False
    ) -> FlowResult:
        """Modify/Delete commands step."""
        return self._show_add_remove_command_form(user_input=user_input, is_add=False)

    @callback
    def _show_main_form(self, errors: dict[str, str] | None = None) -> FlowResult:
        """Handle the main options."""

        options_schema: vol.Schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ROOMS,
                    default=",".join(self._options.get(CONF_ROOMS, [])),
                ): str,  # Multiple rooms are split by commas
            }
        )

        # Add existing commands to the combobox
        option_commands: dict[str, str] = {}
        option_commands[OPTION_LIST_COMMAND] = "--Commands--"
        option_commands[OPTION_ADD_COMMAND] = "Add command..."

        # Propagate the combobox
        for command in self._commands.values():
            name: str = command[CONF_NAME]
            word_or_expression: str | None = command.get(CONF_WORD) or command.get(
                CONF_EXPRESSION
            )
            option_commands[name] = f"{name} ({word_or_expression})"

        config_schema: vol.Schema = options_schema.extend(
            {
                vol.Optional(CONF_COMMANDS, default=OPTION_LIST_COMMAND): vol.In(
                    option_commands
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=config_schema,
            errors=errors,
        )

    @callback
    def _show_add_remove_command_form(
        self, user_input: dict[str, Any] | None, is_add: bool = False
    ) -> FlowResult:
        """
        Add/remove commands step.

        user_input can contain:
        - CONF_NAME: str
        - CONF_WORD: str
        - CONF_EXPRESSION: str
        - CONF_ROOMS: list[str]
        - OPTION_DELETE_COMMAND: bool
        """

        errors: dict[str, str] = {}

        if user_input is None:
            user_input = {}
        else:
            # When entering the step from the main step, the type of user_input[CONF_ROOMS] is list.
            if isinstance(user_input[CONF_ROOMS], str):
                # CONF_ROOMS: convert str to list because voluptuous_serialize does not support List type
                user_input[CONF_ROOMS] = (
                    user_input[CONF_ROOMS].split(",") if user_input[CONF_ROOMS] else []
                )

            try:
                # Check the format of user input
                COMMAND_SCHEMA(user_input)

                if user_input[CONF_NAME] in [*self._commands]:
                    if is_add:
                        # Duplicate name when adding a new command
                        raise DuplicateNameError
                    elif self.__current_command_name is None:
                        # Raise the exception to set self.__current_command_name
                        raise CurrentCommandNameEmpty
                    else:
                        # Duplicate name when modifying the name of an existing command
                        raise DuplicateNameError

            except CurrentCommandNameEmpty:
                # Store the command name that is currently being handled
                self.__current_command_name = user_input[CONF_NAME]
                # Delete the existing command in the temporary list because we will add it back after this step is finished
                del self._commands[str(self.__current_command_name)]

            except DuplicateNameError:
                errors[CONF_NAME] = "duplicate_name"

            else:
                # Store the command in the list (the config will be updated after the user submits the form in the main step)
                if not user_input.get(OPTION_DELETE_COMMAND):
                    self._commands[user_input[CONF_NAME]] = user_input
                # Reset the command name that is currently being handled
                self.__current_command_name = None
                # Return to the main step when a command is created/modified successfully
                return self._show_main_form()

        # When the user is modifying an existing command or any error occurs in this step,
        # user_input will not be None.
        option_schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, "")): str,
                vol.Optional(CONF_WORD, default=user_input.get(CONF_WORD, "")): str,
                vol.Optional(
                    CONF_EXPRESSION, default=user_input.get(CONF_EXPRESSION, "")
                ): str,
                vol.Optional(
                    CONF_ROOMS, default=",".join(user_input.get(CONF_ROOMS, []))
                ): str,  # Multiple rooms are split by commas
            }
        )

        if not is_add:
            # Provide an option to delete the existing command
            option_schema = option_schema.extend(
                {
                    vol.Optional(OPTION_DELETE_COMMAND, default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="add_command" if is_add else "modify_command",
            data_schema=option_schema,
            errors=errors,
        )


class DuplicateNameError(HomeAssistantError):
    """Error to indicate the provided name already exists."""


class CurrentCommandNameEmpty(HomeAssistantError):
    """Error to indicate the current command name is not set."""
