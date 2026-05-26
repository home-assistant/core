"""Options flow for Virtual Remote."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .command import CommandParseError, validate_remote_command_payload
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
)
from .helpers import (
    available_infrared_entities,
    command_options,
    find_command_key,
    infrared_entity_field,
    infrared_entity_field_with_current,
    infrared_entity_selector,
    normalize_command_name,
    normalize_virtual_remotes,
    remote_options,
    remotes_with_commands,
    unique_remote_id,
)

COMMAND_NAME = "command_name"
COMMAND_DATA = "command_data"

SOURCE_ADD_REMOTE = "add_remote"
SOURCE_EDIT_REMOTE = "edit_remote"
SOURCE_REMOVE_REMOTE = "remove_remote"
SOURCE_MANAGE_COMMANDS = "manage_commands"
SOURCE_ADD_COMMAND = "add_command"
SOURCE_EDIT_COMMAND = "edit_command"
SOURCE_REMOVE_COMMAND = "remove_command"


class VirtualRemoteOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Virtual Remote."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._virtual_remotes = normalize_virtual_remotes(
            config_entry.options.get(CONF_VIRTUAL_REMOTES, [])
        )
        self._selected_remote_id: str | None = None
        self._selected_command_name: str | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options menu."""
        menu_options = [SOURCE_ADD_REMOTE]
        if self._virtual_remotes:
            menu_options.extend(
                [
                    SOURCE_EDIT_REMOTE,
                    SOURCE_REMOVE_REMOTE,
                    SOURCE_MANAGE_COMMANDS,
                ]
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_add_remote(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a remote mapped to an infrared entity."""
        errors: dict[str, str] = {}
        infrared_entities = available_infrared_entities(self.hass)

        if not infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"
            elif self._remote_name_exists(name):
                errors[CONF_REMOTE_NAME] = "remote_name_exists"

            if infrared_entity_id not in infrared_entities:
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                self._virtual_remotes.append(
                    {
                        CONF_REMOTE_ID: unique_remote_id(name, self._virtual_remotes),
                        CONF_REMOTE_NAME: name,
                        CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                    }
                )
                return self._create_options_entry()

        remote_name_default = (
            str(user_input.get(CONF_REMOTE_NAME, "")) if user_input else ""
        )
        infrared_entity_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, "")) if user_input else ""
        )

        return self.async_show_form(
            step_id="add_remote",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REMOTE_NAME,
                        default=remote_name_default,
                    ): str,
                    infrared_entity_field(
                        infrared_entity_default,
                        infrared_entities,
                    ): infrared_entity_selector(infrared_entities),
                }
            ),
            errors=errors,
        )

    async def async_step_select_remote_for_edit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote to edit."""
        if not self._virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        if user_input is not None:
            self._selected_remote_id = str(user_input[CONF_REMOTE_ID])
            return await self.async_step_edit_remote()

        return self.async_show_form(
            step_id="select_remote_for_edit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=remote_options(self._virtual_remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_remote(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit a configured remote."""
        errors: dict[str, str] = {}
        remote = self._selected_remote()

        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_edit()
            return self.async_abort(reason="remote_not_found")

        infrared_entities = available_infrared_entities(self.hass)
        if not infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        remote_id = str(remote[CONF_REMOTE_ID])
        current_name = str(remote[CONF_REMOTE_NAME])
        current_entity_id = str(remote[CONF_INFRARED_ENTITY_ID])

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"
            elif self._remote_name_exists(name, current_remote_id=remote_id):
                errors[CONF_REMOTE_NAME] = "remote_name_exists"

            if (
                infrared_entity_id not in infrared_entities
                and infrared_entity_id != current_entity_id
            ):
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                remote[CONF_REMOTE_NAME] = name
                remote[CONF_INFRARED_ENTITY_ID] = infrared_entity_id
                return self._create_options_entry()

        remote_name_default = (
            str(user_input.get(CONF_REMOTE_NAME, current_name))
            if user_input
            else current_name
        )
        infrared_entity_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, current_entity_id))
            if user_input
            else current_entity_id
        )

        return self.async_show_form(
            step_id="edit_remote",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REMOTE_NAME,
                        default=remote_name_default,
                    ): str,
                    infrared_entity_field_with_current(
                        infrared_entity_default,
                        infrared_entities,
                    ): infrared_entity_selector(
                        infrared_entities,
                        current_entity_id=current_entity_id,
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_remote(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Remove a configured remote."""
        if not self._virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        if user_input is not None:
            remote_id = str(user_input[CONF_REMOTE_ID])
            remaining_remotes = [
                remote
                for remote in self._virtual_remotes
                if str(remote.get(CONF_REMOTE_ID)) != remote_id
            ]
            if len(remaining_remotes) == len(self._virtual_remotes):
                return self.async_abort(reason="remote_not_found")

            self._virtual_remotes = remaining_remotes
            return self._create_options_entry()

        return self.async_show_form(
            step_id="remove_remote",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=remote_options(self._virtual_remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_manage_commands(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage command options."""
        source = self.context.get("source")

        if source == SOURCE_ADD_COMMAND:
            return await self.async_step_select_remote_for_command()

        if source == SOURCE_EDIT_COMMAND:
            return await self.async_step_select_remote_for_command_edit()

        if source == SOURCE_REMOVE_COMMAND:
            return await self.async_step_select_remote_for_command_removal()

        menu_options = [SOURCE_ADD_COMMAND]
        if remotes_with_commands(self._virtual_remotes):
            menu_options.extend([SOURCE_EDIT_COMMAND, SOURCE_REMOVE_COMMAND])

        return self.async_show_menu(
            step_id="manage_commands",
            menu_options=menu_options,
        )

    async def async_step_select_remote_for_command(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote before adding a named command."""
        if not self._virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        if user_input is not None:
            self._selected_remote_id = str(user_input[CONF_REMOTE_ID])
            return await self.async_step_add_command()

        return self.async_show_form(
            step_id="select_remote_for_command",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=remote_options(self._virtual_remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_add_command(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a named command for a remote."""
        errors: dict[str, str] = {}
        remote = self._selected_remote()

        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_command()
            return self.async_abort(reason="remote_not_found")

        if user_input is not None:
            command_name = normalize_command_name(str(user_input[COMMAND_NAME]))
            command_data = str(user_input[COMMAND_DATA]).strip()

            if not command_name:
                errors[COMMAND_NAME] = "command_name_required"

            if not command_data:
                errors[COMMAND_DATA] = "command_data_required"

            commands = dict(remote.get(CONF_REMOTE_COMMANDS, {}))
            if not errors and find_command_key(commands, command_name) is not None:
                errors[COMMAND_NAME] = "command_name_exists"

            if not errors:
                try:
                    validate_remote_command_payload(command_data)
                except CommandParseError:
                    errors[COMMAND_DATA] = "invalid_command"

            if not errors:
                commands[command_name] = command_data
                remote[CONF_REMOTE_COMMANDS] = commands
                return self._create_options_entry()

        command_name_default = (
            str(user_input.get(COMMAND_NAME, "")) if user_input else ""
        )
        command_data_default = (
            str(user_input.get(COMMAND_DATA, "")) if user_input else ""
        )

        return self.async_show_form(
            step_id="add_command",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        COMMAND_NAME,
                        default=command_name_default,
                    ): str,
                    vol.Required(
                        COMMAND_DATA,
                        default=command_data_default,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            multiline=True,
                            type=selector.TextSelectorType.TEXT,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select_remote_for_command_edit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote before editing a named command."""
        remotes = remotes_with_commands(self._virtual_remotes)
        if not remotes:
            return self.async_abort(reason="no_remote_commands")

        if user_input is not None:
            self._selected_remote_id = str(user_input[CONF_REMOTE_ID])
            return await self.async_step_select_command_for_edit()

        return self.async_show_form(
            step_id="select_remote_for_command_edit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=remote_options(remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_select_command_for_edit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a named command before editing it."""
        remote = self._selected_remote()
        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_command_edit()
            return self.async_abort(reason="remote_not_found")

        commands = dict(remote.get(CONF_REMOTE_COMMANDS, {}))
        if not commands:
            return self.async_abort(reason="no_remote_commands")

        if user_input is not None:
            self._selected_command_name = str(user_input[COMMAND_NAME])
            return await self.async_step_edit_command()

        return self.async_show_form(
            step_id="select_command_for_edit",
            data_schema=vol.Schema(
                {
                    vol.Required(COMMAND_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=command_options(commands),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_command(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit a named command for a remote."""
        errors: dict[str, str] = {}
        remote = self._selected_remote()

        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_command_edit()
            return self.async_abort(reason="remote_not_found")

        commands = dict(remote.get(CONF_REMOTE_COMMANDS, {}))
        if not commands:
            return self.async_abort(reason="no_remote_commands")

        selected_command_name = self._selected_command_name
        if selected_command_name not in commands:
            if user_input is None:
                return await self.async_step_select_command_for_edit()
            return self.async_abort(reason="command_not_found")

        if user_input is not None:
            command_name = normalize_command_name(str(user_input[COMMAND_NAME]))
            command_data = str(user_input[COMMAND_DATA]).strip()

            if not command_name:
                errors[COMMAND_NAME] = "command_name_required"

            if not command_data:
                errors[COMMAND_DATA] = "command_data_required"

            existing_command_name = find_command_key(commands, command_name)
            if (
                not errors
                and existing_command_name is not None
                and existing_command_name != selected_command_name
            ):
                errors[COMMAND_NAME] = "command_name_exists"

            if not errors:
                try:
                    validate_remote_command_payload(command_data)
                except CommandParseError:
                    errors[COMMAND_DATA] = "invalid_command"

            if not errors:
                commands.pop(selected_command_name, None)
                commands[command_name] = command_data
                remote[CONF_REMOTE_COMMANDS] = commands
                return self._create_options_entry()

        command_name_default = (
            str(user_input.get(COMMAND_NAME, selected_command_name))
            if user_input
            else selected_command_name
        )
        command_data_default = (
            str(user_input.get(COMMAND_DATA, commands[selected_command_name]))
            if user_input
            else str(commands[selected_command_name])
        )

        return self.async_show_form(
            step_id="edit_command",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        COMMAND_NAME,
                        default=command_name_default,
                    ): str,
                    vol.Required(
                        COMMAND_DATA,
                        default=command_data_default,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            multiline=True,
                            type=selector.TextSelectorType.TEXT,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select_remote_for_command_removal(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote before removing a named command."""
        remotes = remotes_with_commands(self._virtual_remotes)
        if not remotes:
            return self.async_abort(reason="no_remote_commands")

        if user_input is not None:
            self._selected_remote_id = str(user_input[CONF_REMOTE_ID])
            return await self.async_step_remove_command()

        return self.async_show_form(
            step_id="select_remote_for_command_removal",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=remote_options(remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_remove_command(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Remove a named command from a remote."""
        remote = self._selected_remote()
        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_command_removal()
            return self.async_abort(reason="remote_not_found")

        commands = dict(remote.get(CONF_REMOTE_COMMANDS, {}))
        if not commands:
            return self.async_abort(reason="no_remote_commands")

        if user_input is not None:
            command_name = str(user_input[COMMAND_NAME])
            if command_name not in commands:
                return self.async_abort(reason="command_not_found")

            commands.pop(command_name)
            if commands:
                remote[CONF_REMOTE_COMMANDS] = commands
            else:
                remote.pop(CONF_REMOTE_COMMANDS, None)
            return self._create_options_entry()

        return self.async_show_form(
            step_id="remove_command",
            data_schema=vol.Schema(
                {
                    vol.Required(COMMAND_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=command_options(commands),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    def _selected_remote(self) -> dict[str, Any] | None:
        """Return the currently selected remote."""
        if self._selected_remote_id is None:
            return None

        return next(
            (
                remote
                for remote in self._virtual_remotes
                if str(remote.get(CONF_REMOTE_ID)) == self._selected_remote_id
            ),
            None,
        )

    def _remote_name_exists(
        self,
        name: str,
        *,
        current_remote_id: str | None = None,
    ) -> bool:
        """Return whether a remote already has this display name."""
        return any(
            str(remote.get(CONF_REMOTE_NAME, "")).casefold() == name.casefold()
            and remote.get(CONF_REMOTE_ID) != current_remote_id
            for remote in self._virtual_remotes
        )

    @callback
    def _create_options_entry(self) -> config_entries.ConfigFlowResult:
        """Create the options entry preserving unrelated options."""
        options = dict(self._config_entry.options)
        options[CONF_VIRTUAL_REMOTES] = self._virtual_remotes
        return self.async_create_entry(title="", data=options)
