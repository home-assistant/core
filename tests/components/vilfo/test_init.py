"""Tests for the Vilfo Router integration setup."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vilfo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vilfo.VilfoClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.mac = "FF-00-00-00-00-00"
        client.get_board_information.return_value = {
            "version": "1.1.0",
            "bootTime": "2024-01-01T00:00:00+00:00",
        }
        client.get_load.return_value = 30
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "testadmin.vilfo.com", "FF-00-00-00-00-00")}
    )
    assert device_entry == snapshot
