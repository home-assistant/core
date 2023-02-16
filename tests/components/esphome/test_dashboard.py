"""Test ESPHome dashboard features."""
from unittest.mock import patch

from aioesphomeapi import DeviceInfo, InvalidAuthAPIError

from homeassistant.components.esphome import CONF_NOISE_PSK, dashboard
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_NOISE_PSK


async def test_new_info_reload_config_entries(
    hass: HomeAssistant, init_integration, mock_dashboard
) -> None:
    """Test config entries are reloaded when new info is set."""
    assert init_integration.state == ConfigEntryState.LOADED

    with patch("homeassistant.components.esphome.async_setup_entry") as mock_setup:
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == init_integration

    # Test it's a no-op when the same info is set
    with patch("homeassistant.components.esphome.async_setup_entry") as mock_setup:
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)

    assert len(mock_setup.mock_calls) == 0


async def test_new_dashboard_fix_reauth(
    hass: HomeAssistant, mock_client, mock_config_entry, mock_dashboard
) -> None:
    """Test config entries waiting for reauth are triggered."""
    mock_client.device_info.side_effect = (
        InvalidAuthAPIError,
        DeviceInfo(uses_password=False, name="test"),
    )

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_init(
            "esphome",
            context={
                "source": SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
                "unique_id": mock_config_entry.unique_id,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert len(mock_get_encryption_key.mock_calls) == 0

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.dashboard.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key, patch(
        "homeassistant.components.esphome.async_setup_entry", return_value=True
    ) as mock_setup:
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)
        await hass.async_block_till_done()

    assert len(mock_get_encryption_key.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1
    assert mock_config_entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_dashboard_supports_update(hass: HomeAssistant, mock_dashboard) -> None:
    """Test dashboard supports update."""
    dash = dashboard.async_get_dashboard(hass)

    # No data
    assert not dash.supports_update

    # supported version
    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
            "current_version": "2023.2.0-dev",
        }
    )
    await dash.async_refresh()

    assert dash.supports_update

    # unsupported version
    mock_dashboard["configured"][0]["current_version"] = "2023.1.0"
    await dash.async_refresh()

    assert not dash.supports_update
