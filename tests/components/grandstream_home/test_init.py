"""Test the Grandstream Home __init__ module."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_gds_api")
async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_gds_api: MagicMock
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_api_ha_control_disabled(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when HA control is disabled."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.grandstream_home.attempt_login",
        return_value=(False, "ha_control_disabled"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_api_offline(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds when device is offline."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "offline"),
        ),
        patch(
            "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
            return_value={"phone_status": "available", "version": "1.0.0"},
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_api_account_locked(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds when account is locked."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "account_locked"),
        ),
        patch(
            "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
            return_value={"phone_status": "available", "version": "1.0.0"},
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_api_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when API raises exception."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.grandstream_home.attempt_login",
        side_effect=OSError("Connection refused"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_product_model(
    hass: HomeAssistant,
    mock_config_entry_with_product_model: MockConfigEntry,
    mock_gds_api: MagicMock,
    device_registry: DeviceRegistry,
) -> None:
    """Test setup with product_model in config data."""
    mock_config_entry_with_product_model.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_product_model.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ec:74:d7:97:53:c5"), mock_config_entry_with_product_model.entry_id
    )
    assert device is not None
    assert device.model == "GDS3710"


async def test_setup_api_invalid_auth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when authentication fails with unrecognized error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.grandstream_home.attempt_login",
        return_value=(False, "invalid_auth"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failed_exception(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator handles exception during update."""
    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        side_effect=RuntimeError("Connection error"),
    ):
        await init_integration.runtime_data.coordinator.async_request_refresh()
        await hass.async_block_till_done()

    assert init_integration.runtime_data.coordinator.last_update_success is False


async def test_coordinator_firmware_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test coordinator updates firmware version in device registry."""
    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={"phone_status": "available", "version": "1.0.0"},
    ):
        await init_integration.runtime_data.coordinator.async_request_refresh()
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.unique_id), init_integration.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.0.0"


async def test_coordinator_null_result(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator handles None result from fetch."""
    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value=None,
    ):
        await init_integration.runtime_data.coordinator.async_request_refresh()
        await hass.async_block_till_done()

    assert init_integration.runtime_data.coordinator.last_update_success is False
