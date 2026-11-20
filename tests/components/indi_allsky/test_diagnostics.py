"""Tests for the diagnostics data provided by the INDI Allsky integration."""

from unittest.mock import AsyncMock

from aioindiallsky import ExposureData, MediaData, SensorData
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    mock_exposure_data: ExposureData,
    mock_sensor_data: SensorData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.latest_exposure = mock_exposure_data
    coordinator.latest_keogram = MediaData(
        media_type="keogram",
        filename="images/keogram_20261011.jpg",
        day_date="20261011",
        night=True,
        camera_id=1,
    )
    coordinator.latest_startrail = MediaData(
        media_type="startrail",
        filename="images/startrail_20261011.jpg",
        day_date="20261011",
        night=True,
        camera_id=1,
    )
    coordinator.latest_sensor = mock_sensor_data
    mock_indi_allsky_client.is_connected = True
    mock_indi_allsky_client.is_control_connected = False

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_empty(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when coordinator data is empty."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.latest_exposure = None
    coordinator.latest_keogram = None
    coordinator.latest_startrail = None
    coordinator.latest_sensor = None

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_redacts_credentials(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test diagnostics redacts host, username, and password."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_USERNAME: "secret_user",
            CONF_PASSWORD: "secret_password",
        },
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result["entry_data"][CONF_HOST] == REDACTED
    assert result["entry_data"][CONF_USERNAME] == REDACTED
    assert result["entry_data"][CONF_PASSWORD] == REDACTED
