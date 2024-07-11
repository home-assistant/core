"""Test ESPHome dashboard features."""

from typing import Any
from unittest.mock import patch

from aioesphomeapi import DeviceInfo, InvalidAuthAPIError

from homeassistant.components.esphome import CONF_NOISE_PSK, coordinator, dashboard
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_NOISE_PSK

from tests.common import MockConfigEntry


async def test_dashboard_storage(
    hass: HomeAssistant,
    init_integration,
    mock_dashboard: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test dashboard storage."""
    assert hass_storage[dashboard.STORAGE_KEY]["data"] == {
        "info": {"addon_slug": "mock-slug", "host": "mock-host", "port": 1234}
    }
    await dashboard.async_set_dashboard_info(hass, "test-slug", "new-host", 6052)
    assert hass_storage[dashboard.STORAGE_KEY]["data"] == {
        "info": {"addon_slug": "test-slug", "host": "new-host", "port": 6052}
    }


async def test_restore_dashboard_storage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Restore dashboard url and slug from storage."""
    hass_storage[dashboard.STORAGE_KEY] = {
        "version": dashboard.STORAGE_VERSION,
        "minor_version": dashboard.STORAGE_VERSION,
        "key": dashboard.STORAGE_KEY,
        "data": {"info": {"addon_slug": "test-slug", "host": "new-host", "port": 6052}},
    }
    with patch.object(
        dashboard, "async_get_or_create_dashboard_manager"
    ) as mock_get_or_create:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_get_or_create.call_count == 1


async def test_restore_dashboard_storage_end_to_end(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Restore dashboard url and slug from storage."""
    hass_storage[dashboard.STORAGE_KEY] = {
        "version": dashboard.STORAGE_VERSION,
        "minor_version": dashboard.STORAGE_VERSION,
        "key": dashboard.STORAGE_KEY,
        "data": {"info": {"addon_slug": "test-slug", "host": "new-host", "port": 6052}},
    }
    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI"
    ) as mock_dashboard_api:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_dashboard_api.mock_calls[0][1][0] == "http://new-host:6052"


async def test_setup_dashboard_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that nothing is stored on failed dashboard setup when there was no dashboard before."""
    with patch.object(
        coordinator.ESPHomeDashboardAPI, "get_devices", side_effect=TimeoutError
    ) as mock_get_devices:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_get_devices.call_count == 1

    # The dashboard addon might recover later so we still
    # allow it to be set up.
    assert dashboard.STORAGE_KEY in hass_storage


async def test_setup_dashboard_fails_when_already_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test failed dashboard setup still reloads entries if one existed before."""
    with patch.object(
        coordinator.ESPHomeDashboardAPI, "get_devices"
    ) as mock_get_devices:
        await dashboard.async_set_dashboard_info(
            hass, "test-slug", "working-host", 6052
        )
        await hass.async_block_till_done()

    assert mock_get_devices.call_count == 1
    assert dashboard.STORAGE_KEY in hass_storage

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch.object(
            coordinator.ESPHomeDashboardAPI, "get_devices", side_effect=TimeoutError
        ) as mock_get_devices,
        patch(
            "homeassistant.components.esphome.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_get_devices.call_count == 1
    # We still setup, and reload, but we do not do the reauths
    assert dashboard.STORAGE_KEY in hass_storage
    assert len(mock_setup.mock_calls) == 1


async def test_new_info_reload_config_entries(
    hass: HomeAssistant, init_integration, mock_dashboard
) -> None:
    """Test config entries are reloaded when new info is set."""
    assert init_integration.state is ConfigEntryState.LOADED

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
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert len(mock_get_encryption_key.mock_calls) == 0

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
            return_value=VALID_NOISE_PSK,
        ) as mock_get_encryption_key,
        patch(
            "homeassistant.components.esphome.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)
        await hass.async_block_till_done()

    assert len(mock_get_encryption_key.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1
    assert mock_config_entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


async def test_dashboard_supports_update(
    hass: HomeAssistant, mock_dashboard: dict[str, Any]
) -> None:
    """Test dashboard supports update."""
    dash = dashboard.async_get_dashboard(hass)

    # No data
    assert not dash.supports_update

    await dash.async_refresh()
    assert dash.supports_update is None

    # supported version
    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
            "current_version": "2023.2.0-dev",
        }
    )
    await dash.async_refresh()
    assert dash.supports_update is True

    # unsupported version
    dash.supports_update = None
    mock_dashboard["configured"][0]["current_version"] = "2023.1.0"
    await dash.async_refresh()

    assert dash.supports_update is False
