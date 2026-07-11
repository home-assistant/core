"""Tests for the Nobø Ecohub integration."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant


async def fire_hub_update(hass: HomeAssistant, hub: MagicMock) -> None:
    """Fire the hub's registered push-update callbacks and wait for state to settle."""
    for call in hub.register_callback.call_args_list:
        call.args[0](hub)
    await hass.async_block_till_done()


async def fire_hub_connection(
    hass: HomeAssistant, hub: MagicMock, connected: bool
) -> None:
    """Fire the hub's registered connection-state callbacks and wait for state to settle."""
    hub.connected = connected
    for call in hub.register_connection_callback.call_args_list:
        call.args[0](hub, connected)
    await hass.async_block_till_done()
