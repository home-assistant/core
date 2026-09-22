"""Electrolux coordinator class."""

from asyncio import Task
from dataclasses import dataclass
import logging
from typing import Any, override

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
from homeassistant.exceptions import HomeAssistantError
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


type ElectroluxConfigEntry = ConfigEntry[ElectroluxData]


class ElectroluxDataUpdateCoordinator(DataUpdateCoordinator[ApplianceState]):
    """Class for fetching appliance data from the API."""

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

    async def send_command(
        self, command: dict[str, Any], max_amount_retries: int = 2, current_try: int = 0
    ) -> None:
        """Send a command to the appliance."""
        try:
            await self.client.send_command(self._appliance_id, command)
        except ApplianceClientException as exception:
            if exception.status in [401, 403]:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="authorization_failed",
                ) from exception
            if exception.status == 406:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_validation_failed",
                ) from exception

            if current_try < max_amount_retries:
                _LOGGER.warning(
                    "Failed to send command to appliance %s. Retrying... (%d/%d)",
                    self._appliance_id,
                    current_try + 1,
                    max_amount_retries,
                )
                # retry the command
                await self.send_command(command, max_amount_retries, current_try + 1)
                # if retry didn't throw an error, return early
                return

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="generic_error",
            ) from exception
