"""Electrolux coordinator class."""

from dataclasses import dataclass
import logging

from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElectroluxApiClient
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class ElectroluxCoordinatorData:
    """Data class for storing coordinator data."""

    appliance_state: ApplianceState


class ElectroluxDataUpdateCoordinator(DataUpdateCoordinator[ElectroluxCoordinatorData]):
    """Class for fetching appliance data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        configEntry: ConfigEntry,
        client: ElectroluxApiClient,
        applianceId: str,
    ) -> None:
        """Initialize."""
        self.client = client
        self._applianceId = applianceId
        super().__init__(
            hass,
            _LOGGER,
            config_entry=configEntry,
            name=f"{DOMAIN}_{configEntry.entry_id}_{applianceId}",
            update_interval=None,
        )

    async def _async_update_data(self) -> ElectroluxCoordinatorData:
        """Return the current appliance state (SSE keeps it updated)."""
        try:
            appliance_state: ApplianceState = await self.client.fetch_appliance_state(
                self._applianceId
            )
            _LOGGER.info(
                "Async update data %s for updates. State: %s",
                self.name,
                appliance_state,
            )
        except Exception as exception:
            raise UpdateFailed(exception) from exception
        else:
            return ElectroluxCoordinatorData(appliance_state)

    def remove_listeners(self) -> None:
        """Remove all SSE listeners."""
        self.client.remove_all_listeners_by_appliance_id(self._applianceId)

    def callback_handle_event(self, event: dict) -> None:
        """Handle an incoming SSE event. Event will look like: {"userId": "...", "applianceId": "...", "property": "timeToEnd", "value": 720}."""

        current_state = self.data.appliance_state
        if not current_state:
            return

        updated_state = self._apply_sse_update(
            current_state,
            event,
        )

        _LOGGER.info(
            "SSE update for %s, property %s, value %s, state: %s",
            self._applianceId,
            event.get("property"),
            event.get("value"),
            updated_state,
        )

        self.async_set_updated_data(ElectroluxCoordinatorData(updated_state))

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
