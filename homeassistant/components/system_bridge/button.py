"""Support for System Bridge buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import (
    BadRequestException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.command_execute import ExecuteRequest
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.settings import SettingsCommandDefinition
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0

COMMAND_KEY_PREFIX = "command_"


@dataclass(frozen=True, kw_only=True)
class SystemBridgeButtonEntityDescription(ButtonEntityDescription):
    """Class describing System Bridge button entities."""

    press_fn: Callable[[WebSocketClient], Awaitable[Response]]


BUTTON_TYPES: tuple[SystemBridgeButtonEntityDescription, ...] = (
    SystemBridgeButtonEntityDescription(
        key="power_sleep",
        translation_key="power_sleep",
        press_fn=lambda client: client.power_sleep(),
    ),
    SystemBridgeButtonEntityDescription(
        key="power_hibernate",
        translation_key="power_hibernate",
        press_fn=lambda client: client.power_hibernate(),
    ),
    SystemBridgeButtonEntityDescription(
        key="power_restart",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda client: client.power_restart(),
    ),
    SystemBridgeButtonEntityDescription(
        key="power_shutdown",
        translation_key="power_shutdown",
        press_fn=lambda client: client.power_shutdown(),
    ),
    SystemBridgeButtonEntityDescription(
        key="power_lock",
        translation_key="power_lock",
        press_fn=lambda client: client.power_lock(),
    ),
    SystemBridgeButtonEntityDescription(
        key="power_logout",
        translation_key="power_logout",
        press_fn=lambda client: client.power_logout(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge buttons based on a config entry."""
    coordinator = entry.runtime_data
    api_port = entry.data[CONF_PORT]
    async_add_entities(
        SystemBridgeButton(coordinator, description, api_port)
        for description in BUTTON_TYPES
    )

    system = coordinator.data.system
    if TYPE_CHECKING:
        assert system is not None
    command_prefix = f"{system.uuid}_{COMMAND_KEY_PREFIX}"
    entity_registry = er.async_get(hass)
    known: set[str] = set()

    @callback
    def _async_check_commands() -> None:
        """Add a button for each new saved command and remove those deleted."""
        if (commands := coordinator.data.commands) is None:
            return
        if new_ids := commands.keys() - known:
            known.update(new_ids)
            async_add_entities(
                SystemBridgeCommandButton(coordinator, api_port, command_id)
                for command_id in new_ids
            )
        # Also catches commands deleted while Home Assistant wasn't running
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if (
                registry_entry.domain == BUTTON_DOMAIN
                and registry_entry.unique_id.startswith(command_prefix)
                and (command_id := registry_entry.unique_id[len(command_prefix) :])
                not in commands
            ):
                known.discard(command_id)
                entity_registry.async_remove(registry_entry.entity_id)

    _async_check_commands()
    entry.async_on_unload(coordinator.async_add_listener(_async_check_commands))


class SystemBridgeButton(SystemBridgeEntity, ButtonEntity):
    """Define a System Bridge button."""

    entity_description: SystemBridgeButtonEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeButtonEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize the System Bridge button."""
        super().__init__(coordinator, api_port, description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Send the power command."""
        try:
            response = await self.entity_description.press_fn(
                self.coordinator.websocket_client
            )
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        if response.type == EventType.ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_command_failed",
                translation_placeholders={"error": response.message or ""},
            )


class SystemBridgeCommandButton(SystemBridgeEntity, ButtonEntity):
    """Define a button that runs a saved command from the host's allowlist."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        command_id: str,
    ) -> None:
        """Initialize the System Bridge command button."""
        super().__init__(coordinator, api_port, f"{COMMAND_KEY_PREFIX}{command_id}")
        self._command_id = command_id
        # Kept so the button still has a name once the command is gone
        self._command_name = self._command.name

    @property
    def _command(self) -> SettingsCommandDefinition:
        """Return the saved command. Only valid while the button is available."""
        commands = self.coordinator.data.commands
        if TYPE_CHECKING:
            assert commands is not None
        return commands[self._command_id]

    @property
    @override
    def name(self) -> str:
        """Return the command's name, which can change in the allowlist."""
        if self.available:
            self._command_name = self._command.name
        return self._command_name

    @property
    @override
    def available(self) -> bool:
        """Return True if the command is still in the allowlist."""
        return super().available and self._command_id in (
            self.coordinator.data.commands or {}
        )

    @override
    async def async_press(self) -> None:
        """Run the saved command."""
        try:
            result = await self.coordinator.websocket_client.execute_command(
                ExecuteRequest(commandID=self._command_id)
            )
        except (ConnectionClosedException, ConnectionResetError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        except ConnectionErrorException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={"name": self.name},
            ) from e
        except BadRequestException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"name": self.name, "error": str(e)},
            ) from e
        if result.error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"name": self.name, "error": result.error},
            )
        if result.exitCode != 0:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_exit_code",
                translation_placeholders={
                    "name": self.name,
                    "exit_code": str(result.exitCode),
                },
            )
