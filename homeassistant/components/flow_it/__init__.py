"""The Flow-it integration."""

import logging

from flow_it_api.client import FlowItVMCMachine
from flow_it_api.exceptions import FlowItConnectionError, FlowItResponseError
from flow_it_api.models import MachineData

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
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

    try:
        # get_info does not require auth, but we want to make sure we can connect
        await vmc.get_info()
    except (FlowItConnectionError, FlowItResponseError) as err:
        raise ConfigEntryNotReady(f"Error connecting to VMC: {err}") from err

    coordinator = FlowItCoordinator(hass, entry, vmc)

    # Initial fetch
    await coordinator.async_config_entry_first_refresh()

    # Setup WebSocket for real-time updates
    async def on_ws_data(data: MachineData) -> None:
        """Handle data from WebSocket."""
        _LOGGER.debug("Received WebSocket update")
        if coordinator.data:
            # Update the internal data of the current state
            coordinator.data.data = data
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
