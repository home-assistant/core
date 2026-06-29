"""The Flow-it integration."""

import logging

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.models import MachineData

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import FlowItConfigEntry, FlowItCoordinator, FlowItData

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.FAN,
]


async def async_setup_entry(hass: HomeAssistant, entry: FlowItConfigEntry) -> bool:
    """Set up Flow-it from a config entry."""

    vmc = FlowItVMCMachine(
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_USERNAME],
        session=get_async_client(hass),
    )

    coordinator = FlowItCoordinator(hass, entry, vmc)

    await coordinator.async_config_entry_first_refresh()

    async def on_ws_data(data: MachineData) -> None:
        """Handle data from WebSocket."""
        _LOGGER.debug("Received WebSocket update")
        if coordinator.data:
            # Update the internal data of the current state
            coordinator.data.state.data = data
            coordinator.async_set_updated_data(coordinator.data)

    vmc.register_websocket_callback(on_ws_data)
    vmc.websocket.start()

    entry.runtime_data = FlowItData(
        vmc=vmc,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlowItConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        vmc = entry.runtime_data.vmc
        # Stop websocket and close client
        vmc.websocket.stop()
        await vmc.close()

    return unload_ok
