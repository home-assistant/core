"""Test ESPHome dashboard features."""

from typing import Any
from unittest.mock import patch

from aioesphomeapi import APIClient, DeviceInfo, InvalidAuthAPIError
import pytest

from homeassistant.components.esphome import CONF_NOISE_PSK, DOMAIN, dashboard
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from . import VALID_NOISE_PSK
from .common import MockDashboardRefresh
from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration", "mock_dashboard")
async def test_dashboard_storage(
    hass: HomeAssistant,
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
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_get_or_create.call_count == 1


async def test_restore_dashboard_storage_end_to_end(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Restore dashboard url and slug from storage."""
    hass_storage[dashboard.STORAGE_KEY] = {
        "version": dashboard.STORAGE_VERSION,
        "minor_version": dashboard.STORAGE_VERSION,
        "key": dashboard.STORAGE_KEY,
        "data": {"info": {"addon_slug": "test-slug", "host": "new-host", "port": 6052}},
    }
    with (
        patch(
            "homeassistant.components.esphome.dashboard.is_hassio", return_value=False
        ),
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI"
        ) as mock_dashboard_api,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_dashboard_api.mock_calls[0][1][0] == "http://new-host:6052"


@pytest.mark.usefixtures("hassio_stubs")
async def test_restore_dashboard_storage_skipped_if_addon_uninstalled(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Restore dashboard restore is skipped if the addon is uninstalled."""
    hass_storage[dashboard.STORAGE_KEY] = {
        "version": dashboard.STORAGE_VERSION,
        "minor_version": dashboard.STORAGE_VERSION,
        "key": dashboard.STORAGE_KEY,
        "data": {"info": {"addon_slug": "test-slug", "host": "new-host", "port": 6052}},
    }
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI"
        ) as mock_dashboard_api,
        patch(
            "homeassistant.components.esphome.dashboard.is_hassio", return_value=True
        ),
        patch(
            "homeassistant.components.hassio.get_addons_info",
            return_value={},
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert "test-slug is no longer installed" in caplog.text
        assert not mock_dashboard_api.called


async def test_setup_dashboard_fails(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test that nothing is stored on failed dashboard setup when there was no dashboard before."""
    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices",
        side_effect=TimeoutError,
    ) as mock_get_devices:
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        await dashboard.async_set_dashboard_info(hass, "test-slug", "test-host", 6052)
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
    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices"
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
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices",
            side_effect=TimeoutError,
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


@pytest.mark.usefixtures("mock_dashboard")
async def test_new_info_reload_config_entries(
    hass: HomeAssistant, init_integration: MockConfigEntry
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
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_config_entry: MockConfigEntry,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test config entries waiting for reauth are triggered."""
    mock_client.device_info.side_effect = (
        InvalidAuthAPIError,
        DeviceInfo(uses_password=False, name="test", mac_address="11:22:33:44:55:AA"),
    )

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert len(mock_get_encryption_key.mock_calls) == 0

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await MockDashboardRefresh(hass).async_refresh()

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
    hass: HomeAssistant,
    mock_dashboard: dict[str, Any],
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test dashboard supports update."""
    dash = dashboard.async_get_dashboard(hass)
    mock_refresh = MockDashboardRefresh(hass)

    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )

    # No data
    assert not dash.supports_update

    await mock_refresh.async_refresh()
    assert dash.supports_update is None

    # supported version
    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
            "current_version": "2023.2.0-dev",
        }
    )

    await mock_refresh.async_refresh()
    assert dash.supports_update is True


async def test_dashboard_unsupported_version(
    hass: HomeAssistant,
    mock_dashboard: dict[str, Any],
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test dashboard with unsupported version."""
    dash = dashboard.async_get_dashboard(hass)
    mock_refresh = MockDashboardRefresh(hass)

    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )

    # No data
    assert not dash.supports_update

    await mock_refresh.async_refresh()
    assert dash.supports_update is None

    # unsupported version
    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
            "current_version": "2023.1.0",
        }
    )
    await mock_refresh.async_refresh()
    assert dash.supports_update is False
