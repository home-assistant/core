"""Test module for IoTMeter config flow in Home Assistant."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.iotmeter.config_flow import EVConfigFlow
from homeassistant.components.iotmeter.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_flow(hass):
    """Fixture for creating a config flow instance."""
    flow = EVConfigFlow()
    flow.hass = hass
    return flow


@pytest.fixture
async def hass(tmpdir):
    """Fixture for Home Assistant instance."""
    hass = HomeAssistant(tmpdir)
    hass.config_entries = config_entries.ConfigEntries(
        hass, {}
    )  # Initialize config_entries with an empty config

    await hass.async_start()
    await hass.async_block_till_done()
    hass.data["integrations"] = {}  # Initialize the 'integrations' key

    yield hass
    await hass.async_stop()


@pytest.mark.asyncio
async def test_async_step_user(mock_config_flow):
    """Test the initial step of the user configuration."""
    with patch.object(
        EVConfigFlow,
        "async_create_entry",
        return_value={
            "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
            "title": "IoTMeter",
            "data": {"ip_address": "192.168.1.1", "port": 8000},
        },
    ) as mock_create_entry:
        user_input = {"ip_address": "192.168.1.1", "port": 8000}
        result = await mock_config_flow.async_step_user(user_input=user_input)

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "IoTMeter"
        assert result["data"] == user_input
        mock_create_entry.assert_called_once_with(title="IoTMeter", data=user_input)

        # Test with invalid input
        invalid_input = {"ip_address": "", "port": 8000}
        result = await mock_config_flow.async_step_user(user_input=invalid_input)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_input"


@pytest.mark.asyncio
async def test_async_step_reconfigure(mock_config_flow, hass):
    """Test the reconfiguration step."""
    mock_config_flow.hass = hass

    # Mock an existing config entry
    entry_id = "12345"
    config_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source=config_entries.SOURCE_USER,
        entry_id=entry_id,
        unique_id=entry_id,
        options={},
    )
    await hass.config_entries.async_add(
        config_entry
    )  # Add the config entry using async_add
    mock_config_flow.context = {"entry_id": entry_id}

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_update_entry",
        return_value=True,
    ) as mock_update_entry:
        user_input = {"ip_address": "192.168.1.2", "port": 9000}
        result = await mock_config_flow.async_step_reconfigure(user_input=user_input)

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reconfigured"
        mock_update_entry.assert_called_once_with(config_entry, data=user_input)

        # Test with invalid input
        invalid_input = {"ip_address": "", "port": 9000}
        result = await mock_config_flow.async_step_reconfigure(user_input=invalid_input)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_input"
