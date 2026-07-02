"""Data update coordinator for the Flow-it integration."""

from dataclasses import dataclass
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


@dataclass
class FlowItCoordinatorData:
    """Data fetched from the Flow-it VMC."""

    state: MachineStatusResponse


class FlowItCoordinator(DataUpdateCoordinator[FlowItCoordinatorData]):
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
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            # get_info does not require auth, but we want to make sure we can connect
            await self.vmc.get_info()
            # Ensure we do validate the authentication
            await self.vmc.refresh_state()
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (FlowItConnectionError, FlowItResponseError) as err:
            raise UpdateFailed(f"Error connecting to VMC: {err}") from err

    @override
    async def _async_update_data(self) -> FlowItCoordinatorData:
        """Fetch data from API endpoint."""
        try:
            await self.vmc.refresh_state()
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (FlowItConnectionError, FlowItResponseError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            assert self.vmc.state is not None
            return FlowItCoordinatorData(state=self.vmc.state)


@dataclass(kw_only=True, frozen=True)
class FlowItData:
    """Data for the Flow-it integration."""

    vmc: FlowItVMCMachine
    coordinator: FlowItCoordinator


type FlowItConfigEntry = ConfigEntry[FlowItData]
