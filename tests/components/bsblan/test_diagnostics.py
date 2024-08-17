"""Tests for the diagnostics data provided by the BSBLan integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan import DOMAIN, HomeAssistantBSBLANData, diagnostics
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    # Create a mock config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        entry_id="test_entry_id",
    )

    # Create mock data
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "state": MagicMock(to_dict=AsyncMock(return_value={"state": "mocked_state"})),
        "sensor": MagicMock(
            to_dict=AsyncMock(return_value={"sensor": "mocked_sensor"})
        ),
    }

    mock_device = AsyncMock(to_dict=AsyncMock(return_value={"device": "mocked_device"}))
    mock_info = AsyncMock(to_dict=AsyncMock(return_value={"info": "mocked_info"}))
    mock_static = AsyncMock(to_dict=AsyncMock(return_value={"static": "mocked_static"}))

    # Create mock BSBLAN data
    mock_bsblan_data = HomeAssistantBSBLANData(
        coordinator=mock_coordinator,
        client=MagicMock(),
        device=mock_device,
        info=mock_info,
        static=mock_static,
    )

    # Add the config entry to hass
    config_entry.add_to_hass(hass)
    hass.data[DOMAIN] = {config_entry.entry_id: mock_bsblan_data}

    # Set up the BSBLAN integration
    with patch("homeassistant.components.bsblan.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Get diagnostics data
    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    # Assert the diagnostics data matches the snapshot
    assert diagnostics_data == snapshot


async def test_diagnostics_no_to_dict(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics when to_dict is not callable."""
    mock_data = MagicMock()
    mock_data.info = "info_string"
    mock_data.device = "device_string"
    mock_data.coordinator = MagicMock()
    mock_data.coordinator.data = {"state": "state_string", "sensor": "sensor_string"}
    mock_data.static = "static_string"

    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_data}

    # Mock the format_mac function to return a predictable value
    with patch(
        "homeassistant.helpers.device_registry.format_mac",
        return_value="00:11:22:33:44:55",
    ):
        diagnostics_data = await diagnostics.async_get_config_entry_diagnostics(
            hass, mock_config_entry
        )

    expected_data = {
        "info": "info_string",
        "device": "device_string",
        "coordinator_data": {
            "state": "state_string",
            "sensor": "sensor_string",
        },
        "static": "static_string",
    }

    assert diagnostics_data == expected_data
