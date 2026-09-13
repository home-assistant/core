"""Test the Škoda integration setup."""

from unittest.mock import AsyncMock, patch

from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient

from homeassistant.components.skoda.coordinator import SkodaUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
) -> None:
    """Test a successful setup and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an authentication failure during setup starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=OpenApiAuthenticationError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_setup_update_failed_starts_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a generic API error during first refresh triggers a setup retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=OpenApiError("boom"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_runtime_data_contents(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
) -> None:
    """Test the runtime data is populated with the expected objects after setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = mock_config_entry.runtime_data
    assert runtime_data.vin == mock_config_entry.unique_id
    assert isinstance(runtime_data.coordinator, SkodaUpdateCoordinator)
    assert isinstance(runtime_data.openapi, OpenAPIClient)
    assert runtime_data.coordinator.data is not None


async def test_setup_forwards_sensor_platform_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
) -> None:
    """Test setup forwards the config entry to the sensor platform only."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_forward.assert_called_once_with(mock_config_entry, [Platform.SENSOR])
