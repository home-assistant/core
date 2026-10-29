"""Data update coordinator for the AriaQ integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.exceptions import (
    FlowItAuthError,
    FlowItConnectionError,
    FlowItResponseError,
)
from flow_it_api.models import MachineData, MachineStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type AriaQConfigEntry = ConfigEntry[AriaQData]


@dataclass(kw_only=True, frozen=True)
class AriaQCoordinatorData:
    """Data fetched from the AriaQ VMC."""

    state: MachineStatusResponse


@dataclass(kw_only=True, frozen=True)
class AriaQData:
    """Data for the AriaQ integration."""

    vmc: FlowItVMCMachine
    coordinator: AriaQCoordinator


class AriaQCoordinator(DataUpdateCoordinator[AriaQCoordinatorData]):
    """Class to manage fetching AriaQ data."""

    config_entry: AriaQConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AriaQConfigEntry,
        vmc: FlowItVMCMachine,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            config_entry=config_entry,
        )
        self.vmc = vmc

        async def _on_ws_data(data: MachineData) -> None:
            """Handle data from WebSocket."""
            _LOGGER.debug("Received WebSocket update")
            if self.data:
                self.data.state.data = data
                self.async_set_updated_data(self.data)

        self.vmc.register_websocket_callback(_on_ws_data)
        self.vmc.websocket.start()

    @override
    async def _async_update_data(self) -> AriaQCoordinatorData:
        """Fetch data from API endpoint."""
        try:
            await self.vmc.refresh_state()
        except FlowItAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except (FlowItConnectionError, FlowItResponseError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        if TYPE_CHECKING:
            assert self.vmc.state is not None
        return AriaQCoordinatorData(state=self.vmc.state)
