"""Tests for the diagnostics data provided by the KNX integration."""
from unittest.mock import patch

from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.knx.conftest import KNXTestKit


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
):
    """Test diagnostics."""
    await knx.setup_integration({})

    with patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        # Overwrite the version for this test since we don't want to change this with every library bump
        knx.xknx.version = "1.0.0"
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        ) == {
            "config_entry_data": {
                "connection_type": "automatic",
                "individual_address": "15.15.250",
                "multicast_group": "224.0.23.12",
                "multicast_port": 3671,
            },
            "configuration_error": None,
            "configuration_yaml": None,
            "xknx": {"current_address": "0.0.0", "version": "1.0.0"},
        }


async def test_diagnostic_config_error(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
):
    """Test diagnostics."""
    await knx.setup_integration({})

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={"knx": {"wrong_key": {}}},
    ):
        # Overwrite the version for this test since we don't want to change this with every library bump
        knx.xknx.version = "1.0.0"
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        ) == {
            "config_entry_data": {
                "connection_type": "automatic",
                "individual_address": "15.15.250",
                "multicast_group": "224.0.23.12",
                "multicast_port": 3671,
            },
            "configuration_error": "extra keys not allowed @ data['knx']['wrong_key']",
            "configuration_yaml": {"wrong_key": {}},
            "xknx": {"current_address": "0.0.0", "version": "1.0.0"},
        }
