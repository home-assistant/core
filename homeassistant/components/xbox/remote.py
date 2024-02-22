"""Xbox Remote support."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import re
from typing import Any

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.smartglass.models import (
    InputKeyType,
    PowerState,
    SmartglassConsole,
    SmartglassConsoleList,
)

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ConsoleData, XboxUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Xbox media_player from a config entry."""
    client: XboxLiveClient = hass.data[DOMAIN][entry.entry_id]["client"]
    consoles: SmartglassConsoleList = hass.data[DOMAIN][entry.entry_id]["consoles"]
    coordinator: XboxUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        [XboxRemote(client, console, coordinator) for console in consoles.result]
    )


class XboxRemote(CoordinatorEntity[XboxUpdateCoordinator], RemoteEntity):
    """Representation of an Xbox remote."""

    def __init__(
        self,
        client: XboxLiveClient,
        console: SmartglassConsole,
        coordinator: XboxUpdateCoordinator,
    ) -> None:
        """Initialize the Xbox Media Player."""
        super().__init__(coordinator)
        self.client: XboxLiveClient = client
        self._console: SmartglassConsole = console

    @property
    def name(self):
        """Return the device name."""
        return f"{self._console.name} Remote"

    @property
    def unique_id(self):
        """Console device ID."""
        return self._console.id

    @property
    def data(self) -> ConsoleData:
        """Return coordinator data for this console."""
        return self.coordinator.data.consoles[self._console.id]

    @property
    def is_on(self):
        """Return True if device is on."""
        return self.data.status.power_state == PowerState.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Xbox on."""
        await self.client.smartglass.wake_up(self._console.id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Xbox off."""
        await self.client.smartglass.turn_off(self._console.id)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send controller or text input to the Xbox."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                try:
                    button = InputKeyType(single_command)
                    await self.client.smartglass.press_button(self._console.id, button)
                except ValueError:
                    await self.client.smartglass.insert_text(
                        self._console.id, single_command
                    )
                await asyncio.sleep(delay)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        # Turns "XboxOneX" into "Xbox One X" for display
        matches = re.finditer(
            ".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)",
            self._console.console_type,
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._console.id)},
            manufacturer="Microsoft",
            model=" ".join([m.group(0) for m in matches]),
            name=self._console.name,
        )
