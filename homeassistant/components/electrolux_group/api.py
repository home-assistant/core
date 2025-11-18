"""Electrolux API Client."""

from collections.abc import Callable
import logging
from typing import Any

from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

from homeassistant.exceptions import HomeAssistantError

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ElectroluxApiClient:
    """Api Client to fetch appliance data."""

    def __init__(self, client: ApplianceClient) -> None:
        """Electrolux API Client."""
        self._client = client

    async def fetch_appliance_data(self) -> list[ApplianceData]:
        """Retrieve all the appliances data from the Electrolux APIs."""
        try:
            appliances = await self._client.get_appliance_data()
        except ApplianceClientException as e:
            appliances = []
            _LOGGER.warning("Failed to get appliances: %s", e)

        # Filter out appliances where details or state is None
        return [
            appliance
            for appliance in appliances
            if appliance.details is not None and appliance.state is not None
        ]

    async def fetch_appliance_state(self, appliance_id: str) -> ApplianceState:
        """Retrieve the appliance state by appliance_id from the Electrolux APIs."""
        return await self._client.get_appliance_state(appliance_id)

    async def send_appliance_command(self, appliance_id: str, command: dict[str, Any]):
        """Send appliance command via Electrolux APIs."""
        try:
            await self._client.send_command(appliance_id, command)
        except ApplianceClientException as e:
            status = getattr(e, "status", None)
            if status:
                raise HomeAssistantError(
                    f"Failed to send command to {appliance_id} (status {status}): {e}"
                ) from e
            raise HomeAssistantError(
                f"Failed to send command to {appliance_id}: {e}"
            ) from e

    async def fetch_interactive_map(self, appliance_id: str):
        """Retrieve the interactive map by appliance_id from the Electrolux APIs."""
        try:
            return await self._client.get_interactive_maps(appliance_id=appliance_id)
        except ApplianceClientException as e:
            _LOGGER.warning(
                "Failed to fetch interactive map for %s: %s", appliance_id, e
            )

    async def fetch_memory_map(self, appliance_id: str):
        """Retrieve the memory map by appliance_id from the Electrolux APIs."""
        try:
            return await self._client.get_memory_maps(appliance_id=appliance_id)
        except ApplianceClientException as e:
            _LOGGER.warning("Failed to fetch memory map for %s: %s", appliance_id, e)

    def add_listener(self, appliance_id: str, callback: Callable[[dict], None]):
        """Register a callback for a specific appliance."""
        self._client.add_listener(appliance_id, callback)

    def remove_all_listeners_by_appliance_id(self, appliance_id: str):
        """Remove all SSE listeners for a specific appliance."""
        self._client.remove_all_listeners_by_appliance_id(appliance_id)
