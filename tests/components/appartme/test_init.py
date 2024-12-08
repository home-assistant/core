"""Test the Appartme integration initialization."""

from unittest.mock import patch

from homeassistant.components.appartme.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from tests.common import HomeAssistant, MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant, mock_appartme_api) -> None:
    """Test setting up the Appartme integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": {"access_token": "test-access-token"}},
        entry_id="test_entry_id",
    )
    config_entry.add_to_hass(hass)

    # Mock API responses
    mock_appartme_api.fetch_devices.return_value = [
        {"deviceId": "device123", "type": "mm", "name": "Main Module"}
    ]
    mock_appartme_api.fetch_device_details.return_value = {
        "deviceId": "device123",
        "type": "mm",
        "name": "Main Module",
        "properties": [
            {"propertyId": "lighting", "mode": "readwrite"},
        ],
    }
    mock_appartme_api.get_device_properties.return_value = {
        "values": [
            {"propertyId": "lighting", "value": False, "mode": "readwrite"},
        ]
    }

    with patch(
        "homeassistant.components.appartme.AppartmePaasClient",
        return_value=mock_appartme_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify the entry state is loaded
    assert config_entry.state == ConfigEntryState.LOADED

    # Verify that the integration was set up
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]
