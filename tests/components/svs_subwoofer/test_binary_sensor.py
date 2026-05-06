"""Tests for the SVS Subwoofer binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, async_init_integration, entity_id


async def test_connected_sensor(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """The connectivity sensor reports 'on' while the BLE client is connected."""
    with patch(
        "homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await async_init_integration(hass)

    state = hass.states.get(
        entity_id(hass, "binary_sensor", SVS_ADDRESS, "connected")
    )
    assert state is not None
    assert state.state == "on"


async def test_disconnect_flips_sensor(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """A BLE disconnect callback flips the sensor to off."""
    with patch(
        "homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        entry = await async_init_integration(hass)

    coordinator = entry.runtime_data
    coordinator._on_disconnect(mock_bleak_client)
    await hass.async_block_till_done()

    state = hass.states.get(
        entity_id(hass, "binary_sensor", SVS_ADDRESS, "connected")
    )
    assert state.state == "off"
