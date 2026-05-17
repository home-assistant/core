"""Options flow for Global Caché iTach IP2IR."""

from collections.abc import Mapping
import re
import time
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .command import CommandParseError, validate_remote_command_payload
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from .pyitach import (
    ItachClient,
    ItachConnectionError,
    ItachError,
    async_get_ir_capability,
)

_REMOTE_ID_RE = re.compile(r"[^a-z0-9_]+")
_COMMAND_NAME_RE = re.compile(r"[^A-Z0-9_]+")
COMMAND_NAME = "command_name"
COMMAND_DATA = "command_data"
SOURCE_ADD_REMOTE = "add_remote"
SOURCE_REMOVE_REMOTE = "remove_remote"
SOURCE_ADD_COMMAND = "add_command"
SOURCE_EDIT_COMMAND = "edit_command"
SOURCE_REMOVE_COMMAND = "remove_command"
SOURCE_REFRESH_INFRARED_PORTS = "refresh_infrared_ports"
SOURCE_CHANGE_REMOTE_INFRARED_ENTITY = "change_remote_infrared_entity"
CONF_LAST_PORT_REFRESH = "last_port_refresh"


class ItachOptionsFlow(config_entries.OptionsFlow):
    """Handle options for iTach IP2IR."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._virtual_remotes: list[dict[str, Any]] = [
            dict(remote)
            for remote in config_entry.options.get(CONF_VIRTUAL_REMOTES, [])
        ]
        self._selected_remote_id: str | None = None
        self._selected_command_name: str | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options menu."""
        source = self.context.get("source")

        if source == SOURCE_ADD_REMOTE:
            return await self.async_step_add_remote()

        if source == SOURCE_REMOVE_REMOTE:
            return await self.async_step_remove_remote()

        if source == SOURCE_ADD_COMMAND:
            return await self.async_step_select_remote_for_command()

        if source == SOURCE_EDIT_COMMAND:
            return await self.async_step_select_remote_for_command_edit()

        if source == SOURCE_REMOVE_COMMAND:
            return await self.async_step_select_remote_for_command_removal()

        if source == SOURCE_REFRESH_INFRARED_PORTS:
            return await self.async_step_refresh_infrared_ports()

        if source == SOURCE_CHANGE_REMOTE_INFRARED_ENTITY:
            return await self.async_step_select_remote_for_infrared_entity()

        menu_options = [SOURCE_REFRESH_INFRARED_PORTS, SOURCE_ADD_REMOTE]
        if self._virtual_remotes:
            menu_options.extend(
                [
                    SOURCE_REMOVE_REMOTE,
                    SOURCE_CHANGE_REMOTE_INFRARED_ENTITY,
                    SOURCE_ADD_COMMAND,
                    SOURCE_EDIT_COMMAND,
                    SOURCE_REMOVE_COMMAND,
                ]
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_refresh_infrared_ports(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Query the iTach and reload entities from current port configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_current_infrared_ports()
            except ItachConnectionError:
                errors["base"] = "cannot_connect"
            except ItachError:
                errors["base"] = "unknown"
            except ValueError:
                errors["base"] = "no_ir_ports"
            else:
                return self._create_options_entry(force_reload=True)

        return self.async_show_form(
            step_id="refresh_infrared_ports",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_add_remote(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a remote mapped to one iTach-owned infrared entity."""
        errors: dict[str, str] = {}
        available_infrared_entities = self._available_infrared_entities()

        if not available_infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        if user_input is not None:
            name = str(user_input[CONF_REMOTE_NAME]).strip()
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()
            remote_id = _slugify_remote_id(name)

            if not name:
                errors[CONF_REMOTE_NAME] = "remote_name_required"
            elif self._remote_name_exists(name) or self._remote_id_exists(remote_id):
                errors[CONF_REMOTE_NAME] = "remote_name_exists"

            if infrared_entity_id not in available_infrared_entities:
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                self._virtual_remotes.append(
                    {
                        CONF_REMOTE_ID: remote_id,
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
                    _infrared_entity_field(
                        infrared_entity_default,
                        available_infrared_entities,
                    ): _infrared_entity_selector(available_infrared_entities),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_remote(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Remove a remote."""
        if not self._virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        if user_input is not None:
            remote_id = str(user_input[CONF_REMOTE_ID])
            self._virtual_remotes = [
                remote
                for remote in self._virtual_remotes
                if str(remote.get(CONF_REMOTE_ID)) != remote_id
            ]
            return self._create_options_entry()

        return self.async_show_form(
            step_id="remove_remote",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_remote_options(self._virtual_remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_select_remote_for_infrared_entity(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote before changing its backing infrared entity."""
        if not self._virtual_remotes:
            return self.async_abort(reason="no_virtual_remotes")

        if user_input is not None:
            self._selected_remote_id = str(user_input[CONF_REMOTE_ID])
            return await self.async_step_change_remote_infrared_entity()

        return self.async_show_form(
            step_id="select_remote_for_infrared_entity",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_remote_options(self._virtual_remotes),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_change_remote_infrared_entity(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Change the backing infrared entity for an existing remote."""
        errors: dict[str, str] = {}
        remote = self._selected_remote()
        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_infrared_entity()
            return self.async_abort(reason="remote_not_found")

        available_infrared_entities = self._available_infrared_entities()
        if not available_infrared_entities:
            return self.async_abort(reason="no_available_infrared_entities")

        if user_input is not None:
            infrared_entity_id = str(user_input[CONF_INFRARED_ENTITY_ID]).strip()
            if infrared_entity_id not in available_infrared_entities:
                errors[CONF_INFRARED_ENTITY_ID] = "infrared_entity_unavailable"

            if not errors:
                remote[CONF_INFRARED_ENTITY_ID] = infrared_entity_id
                return self._create_options_entry()

        current_entity_id = str(remote.get(CONF_INFRARED_ENTITY_ID, ""))
        requested_default = (
            str(user_input.get(CONF_INFRARED_ENTITY_ID, ""))
            if user_input
            else current_entity_id
        )

        return self.async_show_form(
            step_id="change_remote_infrared_entity",
            data_schema=vol.Schema(
                {
                    _infrared_entity_field(
                        requested_default,
                        available_infrared_entities,
                    ): _infrared_entity_selector(available_infrared_entities),
                }
            ),
            errors=errors,
        )

    async def async_step_select_remote_for_command(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a remote before adding or replacing a named command."""
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
                            options=_remote_options(self._virtual_remotes),
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
        """Add or replace a named command for a remote."""
        errors: dict[str, str] = {}
        remote = self._selected_remote()

        if remote is None:
            if user_input is None:
                return await self.async_step_select_remote_for_command()
            return self.async_abort(reason="remote_not_found")

        if user_input is not None:
            command_name = _normalize_command_name(str(user_input[COMMAND_NAME]))
            command_data = str(user_input[COMMAND_DATA]).strip()

            if not command_name:
                errors[COMMAND_NAME] = "command_name_required"

            if not command_data:
                errors[COMMAND_DATA] = "command_data_required"

            if not errors:
                try:
                    validate_remote_command_payload(command_data)
                except CommandParseError:
                    errors[COMMAND_DATA] = "invalid_command"

            if not errors:
                commands = dict(remote.get(CONF_REMOTE_COMMANDS, {}))
                existing_command_name = _find_command_key(commands, command_name)
                if existing_command_name is not None:
                    commands.pop(existing_command_name, None)
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
        remotes_with_commands = _remotes_with_commands(self._virtual_remotes)
        if not remotes_with_commands:
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
                            options=_remote_options(remotes_with_commands),
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
                            options=_command_options(commands),
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
            command_name = _normalize_command_name(str(user_input[COMMAND_NAME]))
            command_data = str(user_input[COMMAND_DATA]).strip()

            if not command_name:
                errors[COMMAND_NAME] = "command_name_required"

            if not command_data:
                errors[COMMAND_DATA] = "command_data_required"

            existing_command_name = _find_command_key(commands, command_name)
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
        remotes_with_commands = _remotes_with_commands(self._virtual_remotes)
        if not remotes_with_commands:
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
                            options=_remote_options(remotes_with_commands),
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
            commands.pop(command_name, None)
            remote[CONF_REMOTE_COMMANDS] = commands
            return self._create_options_entry()

        return self.async_show_form(
            step_id="remove_command",
            data_schema=vol.Schema(
                {
                    vol.Required(COMMAND_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(commands),
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

    def _available_infrared_entities(
        self,
    ) -> dict[str, selector.SelectOptionDict]:
        """Return infrared entities owned by this config entry.

        Multiple virtual remotes may use the same infrared transmitter because
        one physical IR output can control multiple appliances, for example
        through dual emitters or a blaster.
        """
        registry = er.async_get(self.hass)
        options: dict[str, selector.SelectOptionDict] = {}

        for registry_entry in registry.entities.values():
            if registry_entry.domain != "infrared":
                continue
            if registry_entry.platform != DOMAIN:
                continue
            if registry_entry.config_entry_id != self._config_entry.entry_id:
                continue

            entity_id = registry_entry.entity_id
            label = (
                registry_entry.name
                or registry_entry.original_name
                or registry_entry.entity_id
            )
            options[entity_id] = selector.SelectOptionDict(
                value=entity_id,
                label=label,
            )

        return dict(sorted(options.items()))

    async def _validate_current_infrared_ports(self) -> None:
        """Validate current device port configuration has at least one IR port.

        Creating the options entry after this validation triggers the entry update
        listener and reloads the integration. The reload re-queries the device and
        rebuilds infrared entities from the current port configuration.
        """
        host = str(
            self._config_entry.options.get("host", self._config_entry.data["host"])
        )
        port = int(
            self._config_entry.options.get("port", self._config_entry.data["port"])
        )
        client = ItachClient(host, port)

        try:
            ir_capability = await async_get_ir_capability(client)
            if not ir_capability.enabled_ports:
                raise ValueError("No iTach IR output ports are currently available")
        finally:
            await client.close()

    def _remote_name_exists(self, name: str) -> bool:
        """Return whether a remote already has this display name."""
        return any(
            str(remote.get(CONF_REMOTE_NAME, "")).casefold() == name.casefold()
            for remote in self._virtual_remotes
        )

    def _remote_id_exists(self, remote_id: str) -> bool:
        """Return whether a remote already has this id."""
        return any(
            str(remote.get(CONF_REMOTE_ID, "")) == remote_id
            for remote in self._virtual_remotes
        )

    @callback
    def _create_options_entry(
        self,
        *,
        force_reload: bool = False,
    ) -> config_entries.ConfigFlowResult:
        """Create the options entry preserving unrelated options."""
        options = dict(self._config_entry.options)
        options[CONF_VIRTUAL_REMOTES] = self._virtual_remotes
        if force_reload:
            options[CONF_LAST_PORT_REFRESH] = time.time()
        return self.async_create_entry(title="", data=options)


def _slugify_remote_id(name: str) -> str:
    """Create a stable id from a remote name."""
    value = name.strip().casefold().replace(" ", "_")
    value = _REMOTE_ID_RE.sub("_", value)
    value = value.strip("_")
    return value or "remote"


def _normalize_command_name(name: str) -> str:
    """Normalize a user-provided command name."""
    value = name.strip().upper().replace(" ", "_")
    value = _COMMAND_NAME_RE.sub("_", value)
    return value.strip("_")


def _find_command_key(
    commands: Mapping[str, Any],
    normalized_command_name: str,
) -> str | None:
    """Return the existing command key matching a normalized command name."""
    return next(
        (
            command_name
            for command_name in commands
            if _normalize_command_name(str(command_name)) == normalized_command_name
        ),
        None,
    )


def _infrared_entity_selector(
    available_infrared_entities: dict[str, selector.SelectOptionDict],
) -> selector.SelectSelector:
    """Return an infrared entity selector for this entry's IR entities."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(available_infrared_entities.values()),
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _infrared_entity_field(
    default_entity_id: str,
    available_infrared_entities: dict[str, selector.SelectOptionDict],
) -> vol.Required:
    """Return a required infrared entity field with a valid default if possible."""
    if default_entity_id in available_infrared_entities:
        return vol.Required(
            CONF_INFRARED_ENTITY_ID,
            default=default_entity_id,
        )
    return vol.Required(CONF_INFRARED_ENTITY_ID)


def _remotes_with_commands(remotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return remotes which have at least one named command."""
    return [remote for remote in remotes if remote.get(CONF_REMOTE_COMMANDS)]


def _command_options(commands: dict[str, str]) -> list[selector.SelectOptionDict]:
    """Return selector options for command names."""
    return [
        selector.SelectOptionDict(value=command_name, label=command_name)
        for command_name in sorted(commands)
    ]


def _remote_options(remotes: list[dict[str, Any]]) -> list[selector.SelectOptionDict]:
    """Return selector options for remotes."""
    return [
        selector.SelectOptionDict(
            value=str(remote[CONF_REMOTE_ID]),
            label=str(remote[CONF_REMOTE_NAME]),
        )
        for remote in remotes
    ]
