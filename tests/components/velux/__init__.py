"""Tests for the Velux integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.helpers.device_registry import HomeAssistant
from homeassistant.helpers.entity_platform import timedelta

from tests.common import async_fire_time_changed


async def update_callback_entity(
    hass: HomeAssistant, mock_velux_node: MagicMock
) -> None:
    """Simulate an update triggered by the pyvlx lib for a Velux node."""

    callback = mock_velux_node.register_device_updated_cb.call_args[0][0]
    await callback(mock_velux_node)
    await hass.async_block_till_done()


async def update_polled_entities(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Simulate an update trigger from polling."""
    # just fire a time changed event to trigger the polling

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
