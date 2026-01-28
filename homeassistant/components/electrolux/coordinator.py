"""Electrolux coordinator class."""

from __future__ import annotations

from asyncio import Task
from dataclasses import dataclass
import logging

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

from .api import ElectroluxApiClient
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(kw_only=True, slots=True)
class ElectroluxData:
    """Electrolux data type."""

    client: ElectroluxApiClient
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
        client: ElectroluxApiClient,
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
        )

    async def _async_update_data(self) -> ApplianceState:
        """Return the current appliance state (SSE keeps it updated)."""
        try:
            appliance_state = await self.client.fetch_appliance_state(
                self._appliance_id
            )
        except ValueError as exception:
            raise UpdateFailed(exception) from exception
        except ApplianceClientException as exception:
            raise UpdateFailed(exception) from exception
        else:
            return appliance_state

    def remove_listeners(self) -> None:
        """Remove all SSE listeners."""
        self.client.remove_all_listeners_by_appliance_id(self._appliance_id)

    def callback_handle_event(self, event: dict) -> None:
        """Handle an incoming SSE event. Event will look like: {"userId": "...", "applianceId": "...", "property": "timeToEnd", "value": 720}."""

        current_state = self.data
        if not current_state:
            return

        updated_state = self._apply_sse_update(
            current_state,
            event,
        )

        _LOGGER.info(
            "SSE update for %s, property %s, value %s, state: %s",
            self._appliance_id,
            event.get("property"),
            event.get("value"),
            updated_state,
        )

        self.async_set_updated_data(updated_state)

    def _apply_sse_update(self, state: ApplianceState, event: dict) -> ApplianceState:
        """Apply an SSE property update into the appliance state dict and returns the updated state."""
        # Copy state into a dict
        state_dict = state.model_dump()

        prop = event["property"]
        value = event["value"]

        if prop is None:
            _LOGGER.warning("Received SSE event without 'property': %s", event)
            return state

        # Special case: top-level connectionState
        if prop == "connectionState":
            state_dict["connectionState"] = value
        else:
            if prop == "connectivityState":
                state_dict["connectionState"] = value

            # Normal property update
            reported = state_dict.setdefault("properties", {}).setdefault(
                "reported", {}
            )
            path = prop.split("/")  # e.g. ["userSelections", "analogSpinSpeed"]

            target = reported
            for key in path[:-1]:
                target = target.setdefault(key, {})

            target[path[-1]] = value

        # Rebuild a new ApplianceState model from updated dict
        return ApplianceState.model_validate(state_dict)
