"""Support for System Bridge buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.response import Response
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0


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
    async_add_entities(
        SystemBridgeButton(coordinator, description, entry.data[CONF_PORT])
        for description in BUTTON_TYPES
    )


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
