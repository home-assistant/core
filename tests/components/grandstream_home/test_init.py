"""Test the Grandstream Home __init__ module."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_gds_api")
async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not None


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_gds_api: MagicMock
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True


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

    assert mock_config_entry.state.name == "SETUP_RETRY"


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

    assert mock_config_entry.state.name == "LOADED"


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

    assert mock_config_entry.state.name == "LOADED"


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

    assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_setup_with_product_model(
    hass: HomeAssistant, mock_gds_api: MagicMock
) -> None:
    """Test setup with product_model in config data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="GDS3710 EC74D79753C5",
        unique_id="ec:74:d7:97:53:c5",
        data={
            "host": "192.168.1.100",
            "username": "gdsha",
            "password": "password",
            "type": "GDS",
            "model": "GDS3710",
            "port": 443,
            "verify_ssl": False,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "ec:74:d7:97:53:c5")}
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

    assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_firmware_update(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator updates firmware version in device registry."""
    coordinator = init_integration.runtime_data.coordinator

    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.unique_id)}
    )
    assert device is not None
    assert device.sw_version == "1.0.0"


async def test_coordinator_update_failed_exception(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator handles exception during update."""
    coordinator = init_integration.runtime_data.coordinator

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        side_effect=RuntimeError("Connection error"),
    ):
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False


async def test_coordinator_null_result(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test coordinator handles None result from fetch."""
    coordinator = init_integration.runtime_data.coordinator

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value=None,
    ):
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False
