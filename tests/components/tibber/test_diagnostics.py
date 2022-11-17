"""Test the Netatmo diagnostics."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component

from .test_common import mock_connection, mock_connection_with_home

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics_after_failure(
    recorder_mock, hass, hass_client, config_entry
):
    """Test config entry diagnostics."""
    with patch(
        "tibber.Tibber.update_info",
        return_value=None,
    ), patch("homeassistant.components.tibber.discovery.async_load_platform"):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_connection": False,
        "homes": {},
    }


async def test_entry_diagnostics(recorder_mock, hass, hass_client, config_entry):
    """Test config entry diagnostics."""
    with patch(
        "tibber.Tibber",
        side_effect=mock_connection,
    ), patch("homeassistant.components.tibber.discovery.async_load_platform"):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_connection": True,
        "homes": {},
    }


async def test_entry_diagnostics_with_homes(
    recorder_mock, hass, hass_client, config_entry
):
    """Test config entry diagnostics."""
    with patch("tibber.Tibber", side_effect=mock_connection_with_home), patch(
        "homeassistant.components.tibber.discovery.async_load_platform"
    ):
        assert await async_setup_component(hass, "tibber", {})

    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == {
        "api_connection": True,
        "homes": {
            "home_id": {
                "last_data_timestamp": "2016-01-01T12:48:57",
                "has_active_subscription": True,
                "has_real_time_consumption": False,
                "last_cons_data_timestamp": "2016-01-01T12:44:57",
                "country": "NO",
            }
        },
    }
