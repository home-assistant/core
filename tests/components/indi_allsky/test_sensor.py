"""Tests for the INDI Allsky sensor platform."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import ExposureData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_indi_allsky_client"
)
async def test_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_sensor_updates(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor state values update on exposure_complete event."""
    # Enable disabled sensors for testing
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_binmode",
        suggested_object_id="indi_allsky_bin_mode",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_filename",
        suggested_object_id="indi_allsky_filename",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_gain",
        suggested_object_id="indi_allsky_gain",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(mock_exposure_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_exposure_time")
    assert state is not None
    assert state.state == "0.185"

    state = hass.states.get("sensor.indi_allsky_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("sensor.indi_allsky_sky_quality")
    assert state is not None
    assert state.state == "32928.83"

    state = hass.states.get("sensor.indi_allsky_stars")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.indi_allsky_bin_mode")
    assert state is not None
    assert state.state == "1"

    state = hass.states.get("sensor.indi_allsky_filename")
    assert state is not None
    assert state.state == "test.jpg"

    state = hass.states.get("sensor.indi_allsky_gain")
    assert state is not None
    assert state.state == "0.0"
