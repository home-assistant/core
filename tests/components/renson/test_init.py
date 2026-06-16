"""Tests for the Renson integration setup."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.renson.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    all_data = {
        "ModifiedItems": [
            {"Name": "MAC", "Value": "80:7d:3a:bd:1e:32"},
            {"Name": "Device name", "Value": "Endura Delta"},
            {"Name": "Firmware version", "Value": "Firmware version 4.9.1"},
            {"Name": "Hardware version", "Value": "8.0"},
        ]
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.connect.return_value = True
    mock_api.get_all_data.return_value = all_data

    def _get_field_value(data: dict, fieldname: str) -> str:
        for item in data["ModifiedItems"]:
            if item["Name"] == fieldname:
                return item["Value"]
        return ""

    mock_api.get_field_value.side_effect = _get_field_value

    with (
        patch(
            "homeassistant.components.renson.RensonVentilation",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.renson.PLATFORMS",
            [Platform.SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "80:7d:3a:bd:1e:32")}
    )
    assert device_entry == snapshot
