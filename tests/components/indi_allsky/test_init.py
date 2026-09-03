"""Test initialization of INDI Allsky integration."""

from unittest.mock import AsyncMock

from aioindiallsky import ExposureData, IndiAllSkyConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    mock_exposure_data: ExposureData,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_indi_allsky_client.connect.assert_awaited_once()
    mock_indi_allsky_client.listen.assert_called_once_with(auto_reconnect=True)

    coordinator = mock_config_entry.runtime_data
    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(mock_exposure_data)
    await hass.async_block_till_done()

    assert coordinator.data.exposure == mock_exposure_data

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_indi_allsky_client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "method_name",
    ["fetch_image", "connect"],
)
async def test_setup_failure_retry(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method_name: str,
) -> None:
    """Test that an API connection failure during initial setup places entry in retry state."""
    getattr(
        mock_indi_allsky_client, method_name
    ).side_effect = IndiAllSkyConnectionError("Cannot connect to INDI Allsky server")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
