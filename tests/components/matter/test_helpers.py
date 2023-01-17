"""Test the Matter helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.matter.helpers import get_device_id
from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture


async def test_get_device_id(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test get_device_id."""
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    device_id = get_device_id(matter_client.server_info, node.node_devices[0])

    assert device_id == "00000000000004D2-0000000000000005-MatterNodeDevice"
