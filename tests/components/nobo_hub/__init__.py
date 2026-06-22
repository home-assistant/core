"""Tests for the Nobø Ecohub integration."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant


async def fire_hub_update(hass: HomeAssistant, hub: MagicMock) -> None:
    """Fire the hub's registered push-update callbacks and wait for state to settle."""
    for call in hub.register_callback.call_args_list:
        call.args[0](hub)
    await hass.async_block_till_done()
