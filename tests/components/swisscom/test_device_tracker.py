"""Tests for the Swisscom Internet-Box device tracker."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

CLIENT_MAC = "11:22:33:44:55:66"


@pytest.mark.parametrize(
    ("client_name", "expected_entity_id", "expected_device_name"),
    [
        pytest.param("phone", "device_tracker.phone", "phone", id="named"),
        pytest.param(
            None, "device_tracker.11_22_33_44_55_66", CLIENT_MAC, id="unnamed"
        ),
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client_name: str | None,
    expected_entity_id: str,
    expected_device_name: str,
) -> None:
    """Test the tracker describes the tracked device and is named after it."""
    client = MagicMock(
        key=CLIENT_MAC,
        phys_address=CLIENT_MAC,
        ip_address="192.168.1.2",
        active=True,
    )
    client.name = client_name
    mock_swisscom_client.get_devices.return_value = [client]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(expected_entity_id)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}
    assert device.name == expected_device_name
