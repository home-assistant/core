"""Electrolux coordinator class."""

from asyncio import Task
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import override

from electrolux_group_developer_sdk.client.appliance_client import (
    ApplianceClient,
    apply_sse_update,
)
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(kw_only=True, slots=True)
class ElectroluxData:
    """Electrolux data type."""

    client: ApplianceClient
    appliances: list[ApplianceData]
    coordinators: dict[str, ElectroluxDataUpdateCoordinator]
    sse_task: Task
    on_livestream_opening_callback_list: list[Callable[[], Awaitable[None]]]


type ElectroluxConfigEntry = ConfigEntry[ElectroluxData]


class ElectroluxDataUpdateCoordinator(DataUpdateCoordinator[ApplianceState]):
    """Class for fetching appliance data from the API."""

    config_entry: ElectroluxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ElectroluxConfigEntry,
        client: ApplianceClient,
        appliance_id: str,
    ) -> None:
        """Initialize."""
        self.client = client
        self._appliance_id = appliance_id
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}_{appliance_id}",
            update_interval=None,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> ApplianceState:
        """Return the current appliance state (SSE keeps it updated)."""
        try:
            appliance_state = await self.client.get_appliance_state(self._appliance_id)
        except ValueError as exception:
            raise UpdateFailed(exception) from exception
        except ApplianceClientException as exception:
            raise UpdateFailed(exception) from exception
        else:
            return appliance_state

    def add_client_listener(self) -> None:
        """Register an SSE listener to the appliance client for appliance state updates."""
        self.client.add_listener(self._appliance_id, self.callback_handle_event)

    def remove_client_listeners(self) -> None:
        """Remove all SSE listeners."""
        self.client.remove_all_listeners_by_appliance_id(self._appliance_id)

    def callback_handle_event(self, event: dict) -> None:
        """Handle an incoming SSE event. Event will look like: {"userId": "...", "applianceId": "...", "property": "timeToEnd", "value": 720}."""

        current_state = self.data
        if not current_state:
            return

        updated_state = apply_sse_update(
            current_state,
            event,
        )

        self.async_set_updated_data(updated_state)

    def add_livestream_opening_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Add a callback to be called when the livestream opens."""
        self.config_entry.runtime_data.on_livestream_opening_callback_list.append(
            callback
        )

    def remove_livestream_opening_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Remove a callback that was previously added to be called when the livestream opens."""
        self.config_entry.runtime_data.on_livestream_opening_callback_list.remove(
            callback
        )
