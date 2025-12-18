"""Tests for the NRGkick diagnostics."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test diagnostics."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Setup http component for hass_client
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "diagnostics", {})
    await hass.async_block_till_done()

    # Get diagnostics
    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{mock_config_entry.entry_id}"
    )
    assert response.status == 200
    data = await response.json()

    assert "data" in data
    diag_data = data["data"]

    assert "entry" in diag_data
    assert "config" in diag_data
    assert "coordinator" in diag_data
    assert "data" in diag_data

    assert diag_data["entry"]["title"] == "NRGkick Test"
    assert diag_data["data"]["info"] == mock_info_data
