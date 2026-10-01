"""Tests for the INDI Allsky binary sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aioindiallsky import ExposureData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_indi_allsky_client")
async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and binary sensor snapshots using snapshot_platform."""
    with patch(
        "homeassistant.components.indi_allsky._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_binary_sensor_updates(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
) -> None:
    """Test binary sensor state values update on exposure_complete event."""
    with patch(
        "homeassistant.components.indi_allsky._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(mock_exposure_data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.indi_allsky_night")
    assert state is not None
    assert state.state == "off"

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(replace(mock_exposure_data, night=True))
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.indi_allsky_night")
    assert state is not None
    assert state.state == "on"
