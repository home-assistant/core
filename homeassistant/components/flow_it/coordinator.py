"""Data update coordinator for the Flow-it integration."""

from datetime import timedelta
import logging
from typing import override

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.exceptions import (
    FlowItAuthError,
    FlowItConnectionError,
    FlowItResponseError,
)
from flow_it_api.models import MachineStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlowItCoordinator(DataUpdateCoordinator[MachineStatusResponse]):
    """Class to manage fetching Flow-it data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        vmc: FlowItVMCMachine,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            config_entry=config_entry,
        )
        self.vmc = vmc

    @override
    async def _async_update_data(self) -> MachineStatusResponse:
        """Fetch data from API endpoint."""
        try:
            await self.vmc.refresh_state()
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (FlowItConnectionError, FlowItResponseError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return self.vmc.state
