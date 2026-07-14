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
from flow_it_api.models import MachineData, MachineStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type FlowItConfigEntry = ConfigEntry[FlowItData]


@dataclass(kw_only=True, frozen=True)
class FlowItCoordinatorData:
    """Data fetched from the Flow-it VMC."""

    state: MachineStatusResponse


@dataclass(kw_only=True, frozen=True)
class FlowItData:
    """Data for the Flow-it integration."""

    vmc: FlowItVMCMachine
    coordinator: FlowItCoordinator


class FlowItCoordinator(DataUpdateCoordinator[FlowItCoordinatorData]):
    """Class to manage fetching Flow-it data."""

    config_entry: FlowItConfigEntry

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

        async def _on_ws_data(data: MachineData) -> None:
            """Handle data from WebSocket."""
            _LOGGER.debug("Received WebSocket update")
            if self.data:
                self.data.state.data = data
                self.async_set_updated_data(self.data)

        self.vmc.register_websocket_callback(_on_ws_data)
        self.vmc.websocket.start()

    @override
    async def _async_update_data(self) -> FlowItCoordinatorData:
        """Fetch data from API endpoint."""
        try:
            await self.vmc.refresh_state()
            if self.vmc.state is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                )
            return FlowItCoordinatorData(state=self.vmc.state)
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
