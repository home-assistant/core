"""Binary sensor platform dynamic entity tests."""

import pytest
from custom_components.fritzbox_vpn import binary_sensor
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_binary_sensor_adds_on_coordinator_update(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator listener registers new binary sensor entities."""
    coordinator = mock_config_entry.runtime_data.coordinator
    captured_listener = None
    original_add_listener = coordinator.async_add_listener

    def _capture_listener(callback):
        nonlocal captured_listener
        captured_listener = callback
        return original_add_listener(callback)

    coordinator.async_add_listener = _capture_listener
    added: list = []
    await binary_sensor.async_setup_entry(
        hass,
        mock_config_entry,
        lambda entities, **kwargs: added.extend(entities),
    )
    initial = len(added)
    coordinator.data = {
        **MOCK_VPN_CONNECTIONS,
        "conn-new": {
            "uid": "wg-new",
            "name": "New",
            "active": False,
            "connected": False,
        },
    }
    mock_config_entry.runtime_data.known_uids_binary_sensor = set(
        MOCK_VPN_CONNECTIONS.keys()
    )
    captured_listener()
    await hass.async_block_till_done()
    assert len(added) > initial
