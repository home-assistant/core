"""Test the Netatmo diagnostics."""

from unittest.mock import patch

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import API_TYPE_GRAPHQL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_common import mock_get_homes

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    with patch(
        "tibber.Tibber.update_info",
        return_value=None,
    ):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    with patch(
        "tibber.Tibber.get_homes",
        return_value=[],
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_type": API_TYPE_GRAPHQL,
        "homes": [],
    }

    with patch(
        "tibber.Tibber.get_homes",
        side_effect=mock_get_homes,
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_type": API_TYPE_GRAPHQL,
        "homes": [
            {
                "last_data_timestamp": "2016-01-01T12:48:57",
                "has_active_subscription": True,
                "has_real_time_consumption": False,
                "last_cons_data_timestamp": "2016-01-01T12:44:57",
                "country": "NO",
            }
        ],
    }
