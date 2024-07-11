"""Test the Netatmo diagnostics."""

from unittest.mock import patch

from homeassistant.components.recorder import Recorder
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
    with (
        patch(
            "tibber.Tibber.update_info",
            return_value=None,
        ),
        patch("homeassistant.components.tibber.discovery.async_load_platform"),
    ):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    with patch(
        "tibber.Tibber.get_homes",
        return_value=[],
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "homes": [],
    }

    with patch(
        "tibber.Tibber.get_homes",
        side_effect=mock_get_homes,
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
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
